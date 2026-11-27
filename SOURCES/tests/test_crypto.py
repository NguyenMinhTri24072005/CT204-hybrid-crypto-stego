"""Phase 2 tests: src/crypto (BM-03, BM-04, BM-05, BM-10)."""

from __future__ import annotations

import copy
import math

import numpy as np
import pytest

from src.config import load_config
from src.crypto import (
    CIPHER_NAMES,
    AESCipher,
    BaseCipher,
    ChaoticCipher,
    DES3Cipher,
    ciphertext_to_image_view,
    create_cipher,
    derive_bytes,
)
from src.crypto import des3_cipher as des3_module
from src.crypto.chaotic_cipher import ecc_mask, logistic_mask

COINS_SHAPE = (246, 300)  # BM-01: MATLAB coins.png


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(params=CIPHER_NAMES)
def cipher(request, cfg) -> BaseCipher:
    c = create_cipher(request.param, cfg)
    c.warmup()
    return c


def _entropy(data: bytes) -> float:
    counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256)
    p = counts[counts > 0] / counts.sum()
    return float(-(p * np.log2(p)).sum())


# --------------------------------------------------------------------------- derive_bytes
class TestDeriveBytes:
    def test_deterministic_and_length(self):
        a = derive_bytes(2025, 24, "3des:key:0")
        assert a == derive_bytes(2025, 24, "3des:key:0")
        assert isinstance(a, bytes) and len(a) == 24

    def test_zero_length(self):
        assert derive_bytes(2025, 0, "x") == b""

    def test_negative_length_rejected(self):
        with pytest.raises(ValueError):
            derive_bytes(2025, -1, "x")

    def test_domain_separation_by_label(self):
        assert derive_bytes(2025, 16, "aes:key") != derive_bytes(2025, 16, "aes:iv")
        assert derive_bytes(2025, 16, "aes:key") != derive_bytes(2025, 16, "3des:key:0")

    def test_domain_separation_by_seed(self):
        assert derive_bytes(2025, 16, "aes:key") != derive_bytes(2026, 16, "aes:key")

    def test_matches_spec_formula(self):
        import hashlib

        digest = hashlib.sha256(b"7:demo").digest()
        expected = (
            np.random.default_rng(int.from_bytes(digest, "big"))
            .integers(0, 256, size=10, dtype=np.uint8)
            .tobytes()
        )
        assert derive_bytes(7, 10, "demo") == expected


# ------------------------------------------------------------------- common cipher contract
class TestCipherContract:
    @pytest.mark.parametrize("length", [0, 1, 7, 8, 15, 16, 17, 1000, 65536])
    def test_roundtrip(self, cipher, length):
        data = np.random.default_rng(length).integers(0, 256, length, dtype=np.uint8).tobytes()
        assert cipher.decrypt(cipher.encrypt(data)) == data

    def test_roundtrip_coins_sized_image(self, cipher):
        secret = np.random.default_rng(1).integers(0, 256, COINS_SHAPE, dtype=np.uint8)
        pt = np.ascontiguousarray(secret).tobytes()
        recovered = np.frombuffer(cipher.decrypt(cipher.encrypt(pt)), dtype=np.uint8)
        assert np.array_equal(recovered.reshape(COINS_SHAPE), secret)

    @pytest.mark.parametrize("fill", [0x00, 0xFF])
    def test_roundtrip_constant_image(self, cipher, fill):
        # BM-05 edge cases: all-black / all-white secret, size divisible by 8 and 16.
        pt = bytes([fill]) * (64 * 64)
        assert cipher.decrypt(cipher.encrypt(pt)) == pt

    def test_ciphertext_length(self, cipher):
        for length in (0, 1, 15, 16, 73800):
            ct = cipher.encrypt(b"\x00" * length)
            if cipher.block_size is None:
                assert len(ct) == length
            else:
                bs = cipher.block_size
                assert len(ct) % bs == 0
                assert len(ct) == (length // bs + 1) * bs  # PKCS#7 always adds 1..bs bytes

    def test_encrypt_is_deterministic_and_stateless(self, cipher):
        pt = b"hybrid crypto-steganography" * 10
        assert cipher.encrypt(pt) == cipher.encrypt(pt)

    def test_ciphertext_differs_from_plaintext(self, cipher):
        pt = bytes(range(256)) * 4
        assert cipher.encrypt(pt)[: len(pt)] != pt

    def test_ciphertext_looks_random_on_black_image(self, cipher):
        ct = cipher.encrypt(b"\x00" * (COINS_SHAPE[0] * COINS_SHAPE[1]))
        assert _entropy(ct) > 7.99

    def test_same_config_same_ciphertext(self, cipher, cfg):
        other = create_cipher(cipher.name, cfg)
        assert other.encrypt(b"abc" * 50) == cipher.encrypt(b"abc" * 50)

    def test_seed_offset_changes_ciphertext(self, cipher, cfg):
        other = create_cipher(cipher.name, cfg, seed_offset=1)
        assert other.encrypt(b"abc" * 50) != cipher.encrypt(b"abc" * 50)

    def test_is_base_cipher(self, cipher):
        assert isinstance(cipher, BaseCipher)
        assert cipher.name in CIPHER_NAMES


# ------------------------------------------------------------------------------ 3DES
class TestDES3:
    def test_sizes(self, cfg):
        c = DES3Cipher.from_config(cfg)
        assert c.name == "3des" and c.block_size == 8
        assert len(c.key) == 24 and len(c.iv) == 8

    def test_key_has_odd_parity(self, cfg):
        key = DES3Cipher.from_config(cfg).key
        assert all(bin(b).count("1") % 2 == 1 for b in key)

    def test_derived_from_spec_labels(self, cfg):
        seed = cfg["crypto"]["key_seed"]
        c = DES3Cipher.from_config(cfg)
        assert c.iv == derive_bytes(seed, 8, "3des:iv")
        assert c.key == des3_module.DES3.adjust_key_parity(derive_bytes(seed, 24, "3des:key:0"))

    @pytest.mark.parametrize("key_len,iv_len", [(16, 8), (23, 8), (24, 7), (24, 16)])
    def test_rejects_wrong_sizes(self, key_len, iv_len):
        with pytest.raises(ValueError):
            DES3Cipher(b"\x01" * key_len, b"\x02" * iv_len)

    @pytest.mark.parametrize(
        "key",
        [
            b"ABCDEFGH" * 2 + b"12345678",  # K1 == K2
            b"ABCDEFGH" + b"12345678" * 2,  # K2 == K3
        ],
    )
    def test_rejects_degenerate_key(self, key):
        with pytest.raises(ValueError):
            DES3Cipher(key, b"\x00" * 8)

    def test_from_config_skips_degenerate_key(self, cfg, monkeypatch):
        real = des3_module.derive_bytes
        degenerate = b"ABCDEFGH" * 2 + b"12345678"
        labels: list[str] = []

        def fake(seed, length, label):
            labels.append(label)
            if label == "3des:key:0":
                return degenerate
            return real(seed, length, label)

        monkeypatch.setattr(des3_module, "derive_bytes", fake)
        c = DES3Cipher.from_config(cfg)
        assert "3des:key:1" in labels
        assert c.key == des3_module.DES3.adjust_key_parity(
            real(cfg["crypto"]["key_seed"], 24, "3des:key:1")
        )

    @pytest.mark.parametrize("length", [0, 7, 9, 15])
    def test_decrypt_rejects_bad_length(self, cfg, length):
        with pytest.raises(ValueError):
            DES3Cipher.from_config(cfg).decrypt(b"\x00" * length)

    def test_config_size_mismatch(self, cfg):
        bad = copy.deepcopy(cfg)
        bad["crypto"]["des3"]["key_bytes"] = 16
        with pytest.raises(ValueError):
            DES3Cipher.from_config(bad)


# ------------------------------------------------------------------------------- AES
class TestAES:
    def test_sizes(self, cfg):
        c = AESCipher.from_config(cfg)
        assert c.name == "aes" and c.block_size == 16
        assert len(c.key) == 16 and len(c.iv) == 16

    def test_derived_from_spec_labels(self, cfg):
        seed = cfg["crypto"]["key_seed"]
        c = AESCipher.from_config(cfg)
        assert c.key == derive_bytes(seed, 16, "aes:key")
        assert c.iv == derive_bytes(seed, 16, "aes:iv")

    def test_key_independent_from_3des(self, cfg):
        # BM-03 option B pitfall: a shared RNG would make AES key == 3DES key[:16].
        aes, des3 = AESCipher.from_config(cfg), DES3Cipher.from_config(cfg)
        assert aes.key != des3.key[:16]
        assert aes.iv[:8] != des3.iv

    @pytest.mark.parametrize("key_len,iv_len", [(24, 16), (32, 16), (16, 8)])
    def test_rejects_wrong_sizes(self, key_len, iv_len):
        with pytest.raises(ValueError):
            AESCipher(b"\x01" * key_len, b"\x02" * iv_len)

    @pytest.mark.parametrize("length", [0, 8, 15, 17])
    def test_decrypt_rejects_bad_length(self, cfg, length):
        with pytest.raises(ValueError):
            AESCipher.from_config(cfg).decrypt(b"\x00" * length)

    def test_decrypt_wrong_key_fails_or_differs(self, cfg):
        pt = b"secret image bytes" * 20
        ct = AESCipher.from_config(cfg).encrypt(pt)
        other = AESCipher.from_config(cfg, seed_offset=99)
        try:
            assert other.decrypt(ct) != pt
        except ValueError:
            pass  # invalid PKCS#7 padding is the usual outcome

    def test_config_size_mismatch(self, cfg):
        bad = copy.deepcopy(cfg)
        bad["crypto"]["aes"]["key_bytes"] = 32
        with pytest.raises(ValueError):
            AESCipher.from_config(bad)


# --------------------------------------------------------------------------- Chaotic
def _reference_logistic(x0: float, r: float, n: int) -> np.ndarray:
    out, x = [], x0
    for _ in range(n):
        x = r * x * (1.0 - x)
        out.append(min(max(math.floor(x * 256.0), 0), 255))
    return np.array(out, dtype=np.uint8)


class TestChaotic:
    def test_config_parameters(self, cfg):
        c = ChaoticCipher.from_config(cfg)
        assert c.name == "chaotic" and c.block_size is None
        assert c.x0 == 0.785398 and c.r == 3.999 and c.ecc_seed == 42
        assert c.cache_mask is False

    def test_logistic_matches_reference(self):
        assert np.array_equal(
            logistic_mask(0.785398, 3.999, 5000), _reference_logistic(0.785398, 3.999, 5000)
        )

    def test_mask_starts_at_x1(self):
        x1 = 3.999 * 0.785398 * (1.0 - 0.785398)
        assert logistic_mask(0.785398, 3.999, 1)[0] == math.floor(x1 * 256.0)

    def test_mask_clips_x_equal_one(self):
        # x0=0.5, r=4 -> x1 = 1.0 exactly -> floor(256) must clip to 255, then x stays 0.
        assert logistic_mask(0.5, 4.0, 3).tolist() == [255, 0, 0]

    def test_mask_dtype_and_length(self):
        m = logistic_mask(0.785398, 3.999, 100)
        assert m.dtype == np.uint8 and m.shape == (100,)
        assert logistic_mask(0.785398, 3.999, 0).shape == (0,)

    def test_ecc_mask_is_seeded_prng(self):
        expected = np.random.default_rng(42).integers(0, 256, size=64, dtype=np.uint8)
        assert np.array_equal(ecc_mask(42, 64), expected)

    def test_encrypt_is_double_xor(self, cfg):
        c = ChaoticCipher.from_config(cfg)
        pt = np.random.default_rng(3).integers(0, 256, 4096, dtype=np.uint8)
        expected = pt ^ logistic_mask(0.785398, 3.999, 4096) ^ ecc_mask(42, 4096)
        assert c.encrypt(pt.tobytes()) == expected.tobytes()

    def test_empty_input(self, cfg):
        c = ChaoticCipher.from_config(cfg)
        assert c.encrypt(b"") == b"" and c.decrypt(b"") == b""

    def test_seed_offset_shifts_only_ecc_seed(self, cfg):
        c = ChaoticCipher.from_config(cfg, seed_offset=5)
        assert (c.x0, c.r, c.ecc_seed) == (0.785398, 3.999, 47)

    @pytest.mark.parametrize("x0", [0.0, 1.0, -0.1, 1.5])
    def test_rejects_bad_x0(self, x0):
        with pytest.raises(ValueError):
            ChaoticCipher(x0, 3.999, 42)

    @pytest.mark.parametrize("r", [0.0, -1.0, 4.0001])
    def test_rejects_bad_r(self, r):
        with pytest.raises(ValueError):
            ChaoticCipher(0.5, r, 42)

    def test_accepts_r_equal_four(self):
        ChaoticCipher(0.3, 4.0, 1)

    def test_cache_mask_same_output(self, cfg):
        pt = bytes(range(256)) * 50
        plain = ChaoticCipher.from_config(cfg)
        cached = ChaoticCipher.from_config(cfg, cache_mask=True)
        assert cached.encrypt(pt) == plain.encrypt(pt)
        assert cached.decrypt(cached.encrypt(pt)) == pt

    def test_cache_mask_reuses_and_recomputes_by_length(self, cfg):
        c = ChaoticCipher.from_config(cfg, cache_mask=True)
        m1 = c.combined_mask(100)
        assert c.combined_mask(100) is m1  # reused
        m2 = c.combined_mask(200)
        assert m2 is not m1 and m2.shape == (200,)
        assert np.array_equal(m2[:100], m1)  # same keystream prefix

    def test_no_cache_by_default(self, cfg):
        c = ChaoticCipher.from_config(cfg)
        assert c.combined_mask(100) is not c.combined_mask(100)

    def test_warmup(self, cfg):
        ChaoticCipher.from_config(cfg).warmup()


# ---------------------------------------------------------------- ciphertext_to_image_view
class TestImageView:
    def test_truncates_padding(self, cfg):
        aes = AESCipher.from_config(cfg)
        ct = aes.encrypt(b"\x00" * (COINS_SHAPE[0] * COINS_SHAPE[1]))
        assert len(ct) == 73808
        view = ciphertext_to_image_view(ct, COINS_SHAPE)
        assert view.shape == COINS_SHAPE and view.dtype == np.uint8
        assert view.tobytes() == ct[:73800]

    def test_exact_length_stream(self, cfg):
        ct = ChaoticCipher.from_config(cfg).encrypt(b"\x10" * 12)
        assert ciphertext_to_image_view(ct, (3, 4)).tobytes() == ct

    def test_view_is_writable_copy(self):
        view = ciphertext_to_image_view(b"\x01" * 4, (2, 2))
        view[0, 0] = 9  # must not raise (frombuffer arrays are read-only)

    def test_too_short(self):
        with pytest.raises(ValueError):
            ciphertext_to_image_view(b"\x00" * 5, (2, 3))

    @pytest.mark.parametrize("shape", [(0, 3), (3, -1)])
    def test_bad_shape(self, shape):
        with pytest.raises(ValueError):
            ciphertext_to_image_view(b"\x00" * 9, shape)


# --------------------------------------------------------------------------------- factory
class TestFactory:
    @pytest.mark.parametrize(
        "name,cls",
        [("3des", DES3Cipher), ("des3", DES3Cipher), ("3DES", DES3Cipher),
         ("aes", AESCipher), (" AES ", AESCipher), ("chaotic", ChaoticCipher)],
    )
    def test_names_and_aliases(self, cfg, name, cls):
        assert isinstance(create_cipher(name, cfg), cls)

    def test_unknown_name(self, cfg):
        with pytest.raises(ValueError):
            create_cipher("rsa", cfg)

    def test_cache_flag_passthrough(self, cfg):
        assert create_cipher("chaotic", cfg, cache_chaotic_mask=True).cache_mask is True
        assert create_cipher("chaotic", cfg).cache_mask is False

    def test_benchmark_cipher_list_is_supported(self, cfg):
        for name in cfg["benchmark"]["ciphers"]:
            create_cipher(name, cfg)
