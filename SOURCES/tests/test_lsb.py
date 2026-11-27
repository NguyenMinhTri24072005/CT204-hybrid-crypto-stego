"""Phase 3 tests: src/stego/lsb.py (BM-02, BM-06, BM-07)."""

from __future__ import annotations

import ast
import inspect
import struct
import zlib

import numpy as np
import pytest

from src.stego import lsb
from src.stego.lsb import (
    HEADER_BITS,
    EmbedResult,
    choose_num_lsb,
    embed,
    extract,
    pack_header,
    scaled_cover_size,
    unpack_header,
)

H, W = 256, 256
M = H * W * 3  # 196,608 channel values
M_AVAIL = M - HEADER_BITS  # 196,480
CAP_BYTES = {k: M_AVAIL * k // 8 for k in (1, 2, 3)}  # 24,560 / 49,120 / 73,680


@pytest.fixture(scope="module")
def cover() -> np.ndarray:
    return np.random.default_rng(0).integers(0, 256, (H, W, 3), dtype=np.uint8)


def _payload(n: int, seed: int = 1) -> bytes:
    return np.random.default_rng(seed).integers(0, 256, n, dtype=np.uint8).tobytes()


# ------------------------------------------------------------------------------ header
class TestHeader:
    def test_size_and_layout(self):
        hdr = pack_header(2, (246, 300), 73808)
        assert len(hdr) == 16
        magic, ver, k, h, w, n, crc = struct.unpack(">4sBBHHIH", hdr)
        assert (magic, ver, k, h, w, n) == (b"HCST", 1, 2, 246, 300, 73808)
        assert crc == zlib.crc32(hdr[:14]) & 0xFFFF

    def test_roundtrip(self):
        assert unpack_header(pack_header(3, (65535, 1), 2**32 - 1)) == (3, (65535, 1), 2**32 - 1)

    def test_bad_magic(self):
        hdr = bytearray(pack_header(1, (2, 2), 4))
        hdr[0:4] = b"XXXX"
        with pytest.raises(ValueError, match="magic"):
            unpack_header(bytes(hdr))

    @pytest.mark.parametrize("byte_index", [4, 5, 7, 12, 15])
    def test_crc_detects_corruption(self, byte_index):
        hdr = bytearray(pack_header(1, (10, 20), 200))
        hdr[byte_index] ^= 0x01
        with pytest.raises(ValueError, match="CRC"):
            unpack_header(bytes(hdr))

    def test_bad_version_with_valid_crc(self):
        body = struct.pack(">4sBBHHI", b"HCST", 2, 1, 4, 4, 16)
        hdr = body + struct.pack(">H", zlib.crc32(body) & 0xFFFF)
        with pytest.raises(ValueError, match="version"):
            unpack_header(hdr)

    def test_wrong_length(self):
        with pytest.raises(ValueError):
            unpack_header(b"\x00" * 15)

    @pytest.mark.parametrize(
        "k,shape,n",
        [(0, (2, 2), 4), (9, (2, 2), 4), (1, (0, 2), 4), (1, (2, 65536), 4), (1, (2, 2), -1),
         (1, (2, 2), 2**32)],
    )
    def test_pack_rejects_out_of_range(self, k, shape, n):
        with pytest.raises(ValueError):
            pack_header(k, shape, n)


# --------------------------------------------------------------- num_lsb & scale-up
class TestCapacity:
    @pytest.mark.parametrize(
        "n_bytes,expected",
        [(0, 1), (1, 1), (CAP_BYTES[1], 1), (CAP_BYTES[1] + 1, 2), (CAP_BYTES[2], 2),
         (CAP_BYTES[2] + 1, 3), (CAP_BYTES[3], 3), (CAP_BYTES[3] + 1, None)],
    )
    def test_choose_num_lsb_boundaries(self, n_bytes, expected):
        assert choose_num_lsb(M, 8 * n_bytes, 3) == expected

    def test_choose_respects_max_lsb(self):
        assert choose_num_lsb(M, 8 * (CAP_BYTES[1] + 1), 1) is None

    def test_coins_scale_to_257(self):
        # BM-07: 246x300 coins + PKCS#7 = 73,808 B -> cover grows from 256x256 to 257x257.
        assert scaled_cover_size(256, 256, 8 * 73808, 3) == (257, 257)

    @pytest.mark.parametrize("n_bytes", [CAP_BYTES[3] + 1, 100_000, 500_000])
    def test_scaled_size_fits_and_is_minimal(self, n_bytes):
        bits = 8 * n_bytes
        h, w = scaled_cover_size(256, 256, bits, 3)
        assert (3 * h * w - HEADER_BITS) * 3 >= bits
        assert (3 * (h - 1) * (w - 1) - HEADER_BITS) * 3 < bits

    def test_non_square_cover_keeps_aspect(self):
        h, w = scaled_cover_size(100, 200, 8 * 30_000, 3)
        assert abs(w / h - 2.0) < 0.05


# ---------------------------------------------------------------- embed / extract
class TestEmbedExtract:
    @pytest.mark.parametrize(
        "n_bytes,k", [(1, 1), (1000, 1), (CAP_BYTES[1], 1), (CAP_BYTES[1] + 1, 2),
                      (CAP_BYTES[2], 2), (CAP_BYTES[2] + 1, 3), (CAP_BYTES[3], 3)],
    )
    def test_roundtrip_each_num_lsb(self, cover, n_bytes, k):
        ct = _payload(n_bytes)
        res = embed(cover, ct, (7, 9))
        assert isinstance(res, EmbedResult)
        assert res.num_lsb == k and not res.was_scaled_up
        assert res.stego_rgb.shape == cover.shape == res.cover_used_rgb.shape
        assert res.ciphertext_len == n_bytes and res.secret_shape == (7, 9)
        assert extract(res.stego_rgb) == (ct, (7, 9), k)

    @pytest.mark.parametrize("n_bytes", [5, CAP_BYTES[1] + 3, CAP_BYTES[2] + 7, CAP_BYTES[3]])
    def test_only_allowed_bits_change(self, cover, n_bytes):
        res = embed(cover, _payload(n_bytes), (1, 1))
        k = res.num_lsb
        n_used = -(-8 * n_bytes // k)
        diff = (res.stego_rgb ^ cover).reshape(-1)
        assert not np.any(diff[:HEADER_BITS] & 0xFE)  # header: 1 LSB only
        assert not np.any(diff[HEADER_BITS : HEADER_BITS + n_used] & (0xFF ^ ((1 << k) - 1)))
        assert not np.any(diff[HEADER_BITS + n_used :])  # rest untouched

    def test_header_survives_three_lsb_payload(self, cover):
        res = embed(cover, _payload(CAP_BYTES[3]), (3, 4))
        hdr = np.packbits(res.stego_rgb.reshape(-1)[:HEADER_BITS] & 1).tobytes()
        assert unpack_header(hdr) == (3, (3, 4), CAP_BYTES[3])

    def test_payload_starts_at_flat_128(self, cover):
        res = embed(cover, b"\xff", (1, 1))  # 8 one-bits at 1 LSB
        flat = res.stego_rgb.reshape(-1)
        assert np.all(flat[HEADER_BITS : HEADER_BITS + 8] & 1 == 1)

    def test_bit_order_msb_first_within_group(self, cover):
        res = embed(cover, b"\xb4", (1, 1))  # 1011 0100; fits 1 LSB
        flat = res.stego_rgb.reshape(-1)
        assert (flat[HEADER_BITS : HEADER_BITS + 8] & 1).tolist() == [1, 0, 1, 1, 0, 1, 0, 0]

    def test_empty_ciphertext(self, cover):
        res = embed(cover, b"", (1, 1))
        assert res.num_lsb == 1
        assert extract(res.stego_rgb) == (b"", (1, 1), 1)
        assert np.array_equal(res.stego_rgb.reshape(-1)[HEADER_BITS:], cover.reshape(-1)[HEADER_BITS:])

    def test_input_cover_not_modified(self, cover):
        before = cover.copy()
        res = embed(cover, _payload(5000), (1, 1))
        assert np.array_equal(cover, before)
        assert not np.shares_memory(res.stego_rgb, cover)
        assert not np.shares_memory(res.stego_rgb, res.cover_used_rgb)

    def test_scale_up_coins_payload(self, cover):
        ct = _payload(73808)
        res = embed(cover, ct, (246, 300))
        assert res.was_scaled_up and res.num_lsb == 3
        assert res.stego_rgb.shape == res.cover_used_rgb.shape == (257, 257, 3)
        assert extract(res.stego_rgb) == (ct, (246, 300), 3)
        diff = res.stego_rgb ^ res.cover_used_rgb  # stego differs from cover_used only in LSBs
        assert not np.any(diff & 0xF8)

    def test_scale_up_large_payload(self, cover):
        ct = _payload(300_000)
        res = embed(cover, ct, (500, 600))
        assert res.was_scaled_up and res.num_lsb == 3
        assert extract(res.stego_rgb)[0] == ct

    def test_max_lsb_one_scales_earlier(self, cover):
        res = embed(cover, _payload(CAP_BYTES[1] + 1), (1, 1), max_lsb=1)
        assert res.was_scaled_up and res.num_lsb == 1
        assert extract(res.stego_rgb)[2] == 1

    def test_tiny_cover_scales_up(self):
        tiny = np.full((4, 4, 3), 128, dtype=np.uint8)  # 48 channels < 128 header bits
        res = embed(tiny, b"abc", (1, 3))
        assert res.was_scaled_up
        assert extract(res.stego_rgb)[0] == b"abc"

    @pytest.mark.parametrize("interp", ["nearest", "linear", "area", "lanczos", "CUBIC"])
    def test_interpolations(self, cover, interp):
        res = embed(cover, _payload(80_000), (1, 1), interpolation=interp)
        assert extract(res.stego_rgb)[0] == _payload(80_000)


# ------------------------------------------------------------------------ validation
class TestValidation:
    @pytest.mark.parametrize(
        "bad",
        [np.zeros((16, 16), np.uint8), np.zeros((16, 16, 4), np.uint8),
         np.zeros((16, 16, 3), np.float32), np.zeros((16, 16, 3), np.uint16)],
    )
    def test_embed_rejects_bad_cover(self, bad):
        with pytest.raises(ValueError):
            embed(bad, b"x", (1, 1))

    @pytest.mark.parametrize("max_lsb", [0, 9])
    def test_embed_rejects_bad_max_lsb(self, cover, max_lsb):
        with pytest.raises(ValueError):
            embed(cover, b"x", (1, 1), max_lsb=max_lsb)

    def test_embed_rejects_unknown_interpolation(self, cover):
        with pytest.raises(ValueError):
            embed(cover, b"x", (1, 1), interpolation="bogus")

    @pytest.mark.parametrize("shape", [(0, 5), (5, 70000)])
    def test_embed_rejects_bad_secret_shape(self, cover, shape):
        with pytest.raises(ValueError):
            embed(cover, b"x", shape)

    def test_extract_plain_cover_fails(self, cover):
        with pytest.raises(ValueError):
            extract(cover)

    def test_extract_constant_image_fails(self):
        with pytest.raises(ValueError, match="magic"):
            extract(np.zeros((64, 64, 3), np.uint8))

    def test_extract_too_small(self):
        with pytest.raises(ValueError):
            extract(np.zeros((6, 7, 3), np.uint8))  # 126 < 128

    def test_extract_rejects_non_uint8(self):
        with pytest.raises(ValueError):
            extract(np.zeros((64, 64, 3), np.float64))

    def test_extract_detects_flipped_header_bit(self, cover):
        res = embed(cover, _payload(100), (10, 10))
        stego = res.stego_rgb.copy()
        stego.reshape(-1)[100] ^= 1  # inside the CRC-protected length/shape fields
        with pytest.raises(ValueError):
            extract(stego)

    def test_extract_detects_truncated_image(self, cover):
        res = embed(cover, _payload(CAP_BYTES[1]), (1, 1))
        with pytest.raises(ValueError, match="capacity"):
            extract(res.stego_rgb[:128])  # header intact, payload cut off


# ------------------------------------------------------------------ no pixel loops
def test_lsb_module_has_no_python_loops():
    """DoD: no Python loops over pixels/bits anywhere in lsb.py."""
    tree = ast.parse(inspect.getsource(lsb))
    loops = [
        type(n).__name__
        for n in ast.walk(tree)
        if isinstance(n, (ast.For, ast.While, ast.AsyncFor, ast.comprehension))
    ]
    assert loops == []
