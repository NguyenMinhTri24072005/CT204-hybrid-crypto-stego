"""UI business layer: pure Python, independent of Tk windows (unit-testable).

It only *composes* the Phase 1–4 core (crypto, stego, pipeline, metrics); it never changes it.
"""

from __future__ import annotations

import hashlib
import math
import zlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd

from src.crypto import (
    AESCipher,
    BaseCipher,
    ChaoticCipher,
    DES3Cipher,
    ciphertext_to_image_view,
    create_cipher,
    derive_bytes,
)
from src.pipeline import PipelineResult, read_gray, read_rgb, run_pipeline, save_gray_png, save_stego_png
from src.stego.lsb import HEADER_BITS, HEADER_STRUCT, MAGIC, MAX_SUPPORTED_LSB, VERSION, extract

# ------------------------------------------------------------------------- constants
CIPHER_ORDER: tuple[str, ...] = ("3des", "aes", "chaotic")
CIPHER_LABELS = {
    "3des": "3DES-192 (CBC)",
    "aes": "AES-128 (CBC)",
    "chaotic": "Chaotic (Logistic + ECC)",
}
_ALIASES = {"3des": "3des", "des3": "3des", "aes": "aes", "chaotic": "chaotic"}

KEY_MODE_PAPER = "paper_default"
KEY_MODE_PASSPHRASE = "passphrase"
KEY_MODES = (KEY_MODE_PAPER, KEY_MODE_PASSPHRASE)
KEY_MODE_LABELS = {
    KEY_MODE_PAPER: "Chuẩn bài báo (Seed 2025)",
    KEY_MODE_PASSPHRASE: "Mật khẩu tùy chỉnh (Passphrase)",
}

TABLE2_SECRET_SIZE = (156, 156)  # BM-01: fills ~99.1% of the 1-LSB capacity of 256×256×3
MATLAB_COINS_SHAPE = (246, 300)

# Bit of the header flipped by the "flip_header_bit" tamper. The spec text mentions flat[16],
# but bit 16 is the MSB of header byte 2 (inside the magic "HCST"), so the magic would break
# instead of the CRC. Bit 87 is the LSB of byte 10 (ciphertext_len), inside the CRC-protected
# bytes 4..13: the magic stays "HCST" and the CRC-16 check fails, as the demo intends.
HEADER_TAMPER_BIT = 87
PAYLOAD_FLIP_FRACTION = 0.01
GAUSSIAN_SIGMA = 2.0
TAMPER_SEED = 2025

# Raut et al., ICITSC 2025, Table 2 (averages over 8,000 Linnaeus 5 images).
# The paper reports a single "Avg. Entropy" column; it is used for both entropy rows.
PAPER_TABLE2_REFERENCE: dict[str, dict[str, float]] = {
    "3des": {"mse": 0.499975, "psnr": 51.15389, "ssim": 0.998495, "enc_time_s": 0.003552,
             "npcr_enc": 99.59214, "uaci_enc": 30.80843, "corr_enc": 0.00032,
             "entropy_stego": 7.047627, "entropy_enc": 7.047627},
    "aes": {"mse": 0.500006, "psnr": 51.15373, "ssim": 0.998494, "enc_time_s": 0.000601,
            "npcr_enc": 99.61924, "uaci_enc": 30.81756, "corr_enc": -0.00407,
            "entropy_stego": 7.047762, "entropy_enc": 7.047762},
    "chaotic": {"mse": 0.499321, "psnr": 51.14436, "ssim": 0.998099, "enc_time_s": 3.62e-05,
                "npcr_enc": 99.63957, "uaci_enc": 30.96067, "corr_enc": -0.00984,
                "entropy_stego": 6.952836, "entropy_enc": 6.952836},
}
TABLE2_METRICS: tuple[tuple[str, str], ...] = (
    ("mse", "MSE"),
    ("psnr", "PSNR (dB)"),
    ("ssim", "SSIM"),
    ("enc_time_s", "EncTime (s)"),
    ("npcr_enc", "NPCR (%)"),
    ("uaci_enc", "UACI (%)"),
    ("corr_enc", "Correlation"),
    ("entropy_stego", "Entropy Stego"),
    ("entropy_enc", "Entropy Cipher"),
)


# ----------------------------------------------------------------------- key modes
def canonical_cipher_name(name: str) -> str:
    canonical = _ALIASES.get(str(name).strip().lower())
    if canonical is None:
        raise ValueError(f"Thuật toán không hợp lệ: {name!r} (chọn 3des, aes hoặc chaotic)")
    return canonical


def _passphrase_digest(cipher: str, passphrase: str | None) -> bytes:
    if passphrase is None or not str(passphrase).strip():
        raise ValueError("Mật khẩu (passphrase) không được để trống.")
    return hashlib.sha256(f"ct204-ui:{cipher}:{passphrase}".encode("utf-8")).digest()


def build_ui_cipher(
    cipher_name: str,
    cfg: dict[str, Any],
    *,
    key_mode: str = KEY_MODE_PAPER,
    passphrase: str | None = None,
    cache_chaotic_mask: bool = False,
) -> BaseCipher:
    """Cipher for the UI in one of two key modes (spec §3.2).

    - ``paper_default``: exactly ``create_cipher`` (bit-identical to the CLI scripts).
    - ``passphrase``: every cipher's key stream is derived from SHA-256 of the passphrase.
    """
    name = canonical_cipher_name(cipher_name)
    if key_mode == KEY_MODE_PAPER:
        return create_cipher(name, cfg, cache_chaotic_mask=cache_chaotic_mask)
    if key_mode != KEY_MODE_PASSPHRASE:
        raise ValueError(f"Chế độ khóa không hợp lệ: {key_mode!r}")

    digest = _passphrase_digest(name, passphrase)
    seed_int = int.from_bytes(digest[:8], "big")
    if name == "3des":
        iv = derive_bytes(seed_int, 8, "ui:3des:iv")
        for attempt in range(64):
            try:
                return DES3Cipher(derive_bytes(seed_int, 24, f"ui:3des:key:{attempt}"), iv)
            except ValueError:
                continue  # degenerate 3DES key, try the next candidate
        raise RuntimeError("Không dẫn xuất được khóa 3DES hợp lệ từ mật khẩu.")
    if name == "aes":
        return AESCipher(derive_bytes(seed_int, 16, "ui:aes:key"),
                         derive_bytes(seed_int, 16, "ui:aes:iv"))
    x0 = 0.1 + 0.8 * (int.from_bytes(digest[8:16], "big") / 2**64)
    r = float(cfg["crypto"]["chaotic"]["r"])
    return ChaoticCipher(x0=x0, r=r, ecc_seed=int(seed_int & 0x7FFFFFFF),
                         cache_mask=cache_chaotic_mask)


def mutate_passphrase(passphrase: str) -> str:
    """Change exactly one character (the last one) — for the wrong-key demo."""
    if not passphrase:
        return "x"
    last = passphrase[-1]
    changed = chr(ord(last) ^ 1)
    if not changed.isprintable() or changed.isspace():
        changed = "a" if last != "a" else "b"
    return passphrase[:-1] + changed


def build_wrong_key_cipher(
    cipher_name: str,
    cfg: dict[str, Any],
    *,
    key_mode: str = KEY_MODE_PAPER,
    passphrase: str | None = None,
    cache_chaotic_mask: bool = False,
) -> tuple[BaseCipher, str]:
    """A deliberately wrong key of the same cipher, plus a Vietnamese description."""
    name = canonical_cipher_name(cipher_name)
    if key_mode == KEY_MODE_PASSPHRASE:
        wrong = mutate_passphrase(str(passphrase or ""))
        cipher = build_ui_cipher(name, cfg, key_mode=KEY_MODE_PASSPHRASE, passphrase=wrong,
                                 cache_chaotic_mask=cache_chaotic_mask)
        return cipher, f"Mật khẩu lệch đúng 1 ký tự: “{wrong}”"
    seed = int(cfg["crypto"]["key_seed"])
    cipher = create_cipher(name, cfg, seed_offset=1, cache_chaotic_mask=cache_chaotic_mask)
    if name == "chaotic":
        ecc = int(cfg["crypto"]["chaotic"]["ecc_seed"])
        return cipher, f"ECC seed {ecc + 1} thay vì {ecc}"
    return cipher, f"Khóa dẫn xuất từ seed {seed + 1} thay vì {seed}"


# -------------------------------------------------------------------------- images
def normalize_cover(cover_rgb: np.ndarray, cfg: dict[str, Any]) -> np.ndarray:
    """Resize the cover to ``stego.cover_size`` (256×256 in the paper) with INTER_AREA."""
    h, w = (int(v) for v in cfg["stego"]["cover_size"])
    if cover_rgb.shape[:2] == (h, w):
        return np.ascontiguousarray(cover_rgb, dtype=np.uint8)
    return np.ascontiguousarray(cv2.resize(cover_rgb, (w, h), interpolation=cv2.INTER_AREA))


def resize_secret(secret_gray: np.ndarray, size: tuple[int, int] | None) -> np.ndarray:
    if size is None or tuple(secret_gray.shape[:2]) == tuple(size):
        return np.ascontiguousarray(secret_gray, dtype=np.uint8)
    h, w = int(size[0]), int(size[1])
    if h <= 0 or w <= 0:
        raise ValueError(f"Kích thước secret không hợp lệ: {size}")
    return np.ascontiguousarray(cv2.resize(secret_gray, (w, h), interpolation=cv2.INTER_AREA))


def matlab_coins_in_memory() -> np.ndarray:
    """MATLAB-like 246×300 coins image built in RAM (never written to disk)."""
    from skimage import data as skdata

    return np.ascontiguousarray(cv2.resize(
        skdata.coins(), (MATLAB_COINS_SHAPE[1], MATLAB_COINS_SHAPE[0]),
        interpolation=cv2.INTER_AREA))


def sample_cover_path(cfg: dict[str, Any]) -> Path:
    return Path(cfg["paths"]["sample_dir"]) / "cover.jpg"


def load_sample_cover(cfg: dict[str, Any]) -> np.ndarray:
    return read_rgb(sample_cover_path(cfg))


def load_sample_secret(cfg: dict[str, Any]) -> np.ndarray:
    path = Path(cfg["secret"]["path"])
    return read_gray(path) if path.is_file() else matlab_coins_in_memory()


def compute_diff_heatmap(cover_used_rgb: np.ndarray, stego_rgb: np.ndarray,
                         gain: float = 50.0) -> np.ndarray:
    """``|cover − stego| × gain`` clipped to uint8 so LSB-carrying pixels become visible."""
    a = np.asarray(cover_used_rgb)
    b = np.asarray(stego_rgb)
    if a.shape != b.shape:
        raise ValueError(f"Kích thước không khớp: {a.shape} vs {b.shape}")
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16)).astype(np.float32) * float(gain)
    return np.clip(diff, 0, 255).astype(np.uint8)


build_diff_heatmap = compute_diff_heatmap


def compare_images(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    """MSE, PSNR, bit error rate and exactness between two equally shaped uint8 images."""
    ref = np.asarray(reference, dtype=np.uint8)
    cand = np.asarray(candidate, dtype=np.uint8)
    if ref.shape != cand.shape:
        raise ValueError(f"Kích thước không khớp: {ref.shape} vs {cand.shape}")
    diff = ref.astype(np.float64) - cand.astype(np.float64)
    mse = float(np.mean(diff * diff))
    psnr = float("inf") if mse == 0.0 else 10.0 * math.log10(255.0**2 / mse)
    bit_errors = int(np.unpackbits(np.bitwise_xor(ref, cand).reshape(-1)).sum())
    return {"mse": mse, "psnr": psnr, "bit_error_rate": bit_errors / (ref.size * 8),
            "is_exact": bool(np.array_equal(ref, cand))}


# ------------------------------------------------------------------- encrypt flow
@dataclass
class EncryptWorkflowResult:
    cipher_name: str
    key_mode: str
    pipeline: PipelineResult
    diff_heatmap: np.ndarray
    cover_input_shape: tuple[int, ...]
    diff_gain: float = 50.0

    @property
    def cipher_label(self) -> str:
        return CIPHER_LABELS[self.cipher_name]

    @property
    def metrics(self) -> dict[str, float]:
        return self.pipeline.metrics

    @property
    def stego_rgb(self) -> np.ndarray:
        return self.pipeline.stego_rgb

    @property
    def cover_used_rgb(self) -> np.ndarray:
        return self.pipeline.cover_used_rgb

    @property
    def secret_gray(self) -> np.ndarray:
        return self.pipeline.secret

    @property
    def encrypted_view(self) -> np.ndarray:
        return self.pipeline.encrypted_view

    @property
    def recovered(self) -> np.ndarray:
        return self.pipeline.recovered

    @property
    def num_lsb(self) -> int:
        return self.pipeline.embed.num_lsb

    @property
    def ciphertext_len(self) -> int:
        return len(self.pipeline.ciphertext)

    @property
    def was_scaled_up(self) -> bool:
        return self.pipeline.embed.was_scaled_up

    @property
    def enc_time_s(self) -> float:
        return self.pipeline.enc_time_s

    @property
    def is_exact(self) -> bool:
        return self.pipeline.is_exact


def run_encrypt_workflow(
    cover_rgb: np.ndarray,
    secret_gray: np.ndarray,
    cfg: dict[str, Any],
    *,
    cipher_name: str = "aes",
    key_mode: str = KEY_MODE_PAPER,
    passphrase: str | None = None,
    cache_chaotic_mask: bool = False,
    normalize: bool = True,
    secret_size: tuple[int, int] | None = None,
    diff_gain: float = 50.0,
) -> EncryptWorkflowResult:
    """encrypt (timed) → embed → extract → decrypt → metrics, entirely in RAM."""
    name = canonical_cipher_name(cipher_name)
    cipher = build_ui_cipher(name, cfg, key_mode=key_mode, passphrase=passphrase,
                             cache_chaotic_mask=cache_chaotic_mask)
    cover = normalize_cover(cover_rgb, cfg) if normalize else np.ascontiguousarray(cover_rgb)
    secret = resize_secret(secret_gray, secret_size)
    stego_cfg = cfg["stego"]
    result = run_pipeline(
        secret, cover, cipher,
        max_lsb=int(stego_cfg["max_lsb"]),
        interpolation=str(stego_cfg.get("scale_up_interpolation", "cubic")),
        compute_metrics=True, warmup=True,
    )
    return EncryptWorkflowResult(
        cipher_name=name, key_mode=key_mode, pipeline=result,
        diff_heatmap=compute_diff_heatmap(result.cover_used_rgb, result.stego_rgb, diff_gain),
        cover_input_shape=tuple(np.asarray(cover_rgb).shape), diff_gain=diff_gain,
    )


# ---------------------------------------------------------------- header inspector
@dataclass
class HeaderInspection:
    is_valid: bool
    magic_raw: bytes
    version: int | None
    num_lsb: int | None
    secret_shape: tuple[int, int] | None
    ciphertext_len: int | None
    crc_expected: int | None  # CRC-16 recomputed from header bytes 0..13
    crc_actual: int | None  # CRC-16 stored in header bytes 14..15
    error_message: str | None
    raw_header: bytes = b""

    @property
    def magic_text(self) -> str:
        return "".join(chr(b) if 32 <= b < 127 else "·" for b in self.magic_raw)

    @property
    def crc_ok(self) -> bool:
        return self.crc_expected is not None and self.crc_expected == self.crc_actual

    @property
    def status_text(self) -> str:
        return "HỢP LỆ ✅" if self.is_valid else "LỖI TOÀN VẸN ❌"


def inspect_stego_header(stego_rgb: np.ndarray) -> HeaderInspection:
    """Parse the 16-byte header at 1 LSB of ``flat[0:128]`` without raising (spec §3.3)."""
    arr = np.asarray(stego_rgb)
    empty = HeaderInspection(False, b"", None, None, None, None, None, None, None)
    if arr.dtype != np.uint8:
        empty.error_message = f"Ảnh phải là uint8, nhận {arr.dtype}."
        return empty
    flat = np.ascontiguousarray(arr).reshape(-1)
    if flat.size < HEADER_BITS:
        empty.error_message = f"Ảnh quá nhỏ: {flat.size} < {HEADER_BITS} giá trị kênh để chứa Header."
        return empty

    raw = np.packbits(flat[:HEADER_BITS] & 1).tobytes()
    magic, version, num_lsb, h, w, ct_len, crc_stored = HEADER_STRUCT.unpack(raw)
    crc_calc = zlib.crc32(raw[:14]) & 0xFFFF
    if magic != MAGIC:
        return HeaderInspection(
            False, magic, None, None, None, None, None, None,
            f"Sai chữ ký Magic: đọc được {magic!r} thay vì {MAGIC!r} — ảnh không chứa tin "
            "hoặc LSB đã bị phá hủy (nén JPEG / nhiễu).", raw)

    info = HeaderInspection(True, magic, version, num_lsb, (h, w), ct_len, crc_calc, crc_stored,
                            None, raw)
    if crc_calc != crc_stored:
        info.is_valid = False
        info.error_message = (f"CRC-16 mismatch: tính lại 0x{crc_calc:04X} ≠ lưu trong Header "
                              f"0x{crc_stored:04X} — metadata đã bị giả mạo/hỏng.")
    elif version != VERSION:
        info.is_valid = False
        info.error_message = f"Phiên bản Header không hỗ trợ: {version} (cần {VERSION})."
    elif not 1 <= num_lsb <= MAX_SUPPORTED_LSB:
        info.is_valid = False
        info.error_message = f"num_lsb không hợp lệ: {num_lsb}."
    elif h == 0 or w == 0:
        info.is_valid = False
        info.error_message = f"Kích thước secret không hợp lệ: {h}×{w}."
    elif HEADER_BITS + math.ceil(8 * ct_len / num_lsb) > flat.size:
        info.is_valid = False
        info.error_message = (f"Header khai {ct_len:,} byte ở {num_lsb}-LSB, vượt sức chứa ảnh "
                              f"({flat.size:,} kênh).")
    return info


# ------------------------------------------------------------------- decrypt flow
@dataclass
class DecryptWorkflowResult:
    success: bool
    stage: str  # "header" | "extract" | "decrypt" | "ok"
    cipher_name: str
    key_mode: str
    header: HeaderInspection
    message: str
    recovered: np.ndarray | None = None
    raw_corrupted_preview: np.ndarray | None = None
    secret_shape: tuple[int, int] | None = None
    num_lsb: int | None = None
    ciphertext_len: int | None = None
    dec_time_s: float | None = None
    recovery_mse: float | None = None
    recovery_psnr: float | None = None
    bit_error_rate: float | None = None
    is_exact: bool | None = None
    key_description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def display_image(self) -> np.ndarray | None:
        return self.recovered if self.recovered is not None else self.raw_corrupted_preview


def _raw_block_decrypt(cipher: BaseCipher, ciphertext: bytes) -> bytes | None:
    """CBC decryption WITHOUT unpadding (to show the noise produced by a wrong key)."""
    from Crypto.Cipher import AES, DES3

    if isinstance(cipher, AESCipher):
        module, block = AES, 16
    elif isinstance(cipher, DES3Cipher):
        module, block = DES3, 8
    else:
        return None
    if not ciphertext or len(ciphertext) % block:
        return None
    return module.new(cipher.key, module.MODE_CBC, iv=cipher.iv).decrypt(ciphertext)


def run_decrypt_workflow(
    stego_rgb: np.ndarray,
    cfg: dict[str, Any],
    *,
    cipher_name: str = "aes",
    key_mode: str = KEY_MODE_PAPER,
    passphrase: str | None = None,
    reference_secret_gray: np.ndarray | None = None,
    cipher: BaseCipher | None = None,
    key_description: str = "",
    cache_chaotic_mask: bool = False,
) -> DecryptWorkflowResult:
    """extract → decrypt → reshape, reporting failures instead of raising (spec §3.3).

    A wrong key on AES/3DES usually breaks PKCS#7 unpadding; the result then carries
    ``raw_corrupted_preview`` (CBC output without unpad) so the UI can show the noise.
    """
    import time

    name = canonical_cipher_name(cipher.name if cipher is not None else cipher_name)
    header = inspect_stego_header(stego_rgb)
    base = dict(cipher_name=name, key_mode=key_mode, header=header, key_description=key_description)
    if not header.is_valid:
        return DecryptWorkflowResult(success=False, stage="header",
                                     message=header.error_message or "Header không hợp lệ.", **base)
    try:
        ciphertext, shape, num_lsb = extract(stego_rgb)
    except ValueError as exc:
        return DecryptWorkflowResult(success=False, stage="extract", message=str(exc), **base)
    if cipher is None:
        cipher = build_ui_cipher(name, cfg, key_mode=key_mode, passphrase=passphrase,
                                 cache_chaotic_mask=cache_chaotic_mask)
    base.update(secret_shape=shape, num_lsb=num_lsb, ciphertext_len=len(ciphertext))
    h, w = shape

    t0 = time.perf_counter()
    try:
        plaintext = cipher.decrypt(ciphertext)
        error: str | None = None
    except ValueError as exc:
        plaintext, error = None, str(exc)
    dec_time = time.perf_counter() - t0

    out: DecryptWorkflowResult
    if plaintext is not None and len(plaintext) == h * w:
        recovered = np.frombuffer(plaintext, dtype=np.uint8).reshape(h, w).copy()
        out = DecryptWorkflowResult(success=True, stage="ok", recovered=recovered,
                                    dec_time_s=dec_time,
                                    message="Trích xuất & giải mã hoàn tất.", **base)
    else:
        raw = _raw_block_decrypt(cipher, ciphertext)
        preview = None
        source = raw if raw is not None else plaintext
        if source is not None and len(source) >= h * w:
            preview = ciphertext_to_image_view(source, shape)
        if error is not None:
            msg = (f"Lỗi xác thực PKCS#7 padding ({error}) — gần như chắc chắn do SAI KHÓA "
                   "hoặc payload bị sửa: khối CBC cuối giải mã ra rác nên không gỡ được padding.")
        else:
            got = 0 if plaintext is None else len(plaintext)
            msg = (f"Độ dài bản rõ {got:,} byte không khớp kích thước secret {h}×{w} = {h * w:,} "
                   "byte — sai khóa hoặc payload bị sửa.")
        out = DecryptWorkflowResult(success=False, stage="decrypt", message=msg,
                                    raw_corrupted_preview=preview, dec_time_s=dec_time, **base)

    image = out.display_image
    if reference_secret_gray is not None and image is not None:
        ref = np.asarray(reference_secret_gray, dtype=np.uint8)
        if ref.shape == image.shape:
            stats = compare_images(ref, image)
            out.recovery_mse = stats["mse"]
            out.recovery_psnr = stats["psnr"]
            out.bit_error_rate = stats["bit_error_rate"]
            out.is_exact = stats["is_exact"] and out.success
            if out.success and not out.is_exact:
                out.message = ("Giải mã chạy xong nhưng ảnh khác ảnh gốc "
                               f"(MSE = {out.recovery_mse:,.2f}) — sai khóa hoặc payload bị sửa.")
        else:
            out.extra["reference_shape_mismatch"] = (ref.shape, image.shape)
    return out


# --------------------------------------------------------------------- tamper lab
TAMPER_MODES: dict[str, str] = {
    "jpeg_q95": "Nén JPEG chất lượng 95",
    "flip_header_bit": "Đảo 1 bit LSB trong vùng CRC của Header",
    "flip_payload_bits": "Đảo 1% bit LSB của payload",
    "gaussian_noise": "Cộng nhiễu Gaussian σ = 2.0",
}


def simulate_tamper(stego_rgb: np.ndarray, mode: str) -> tuple[np.ndarray, str]:
    """Return a tampered COPY of the stego image (RAM only) and a Vietnamese explanation."""
    src = np.ascontiguousarray(np.asarray(stego_rgb, dtype=np.uint8))
    if src.ndim != 3 or src.shape[2] != 3:
        raise ValueError(f"Ảnh stego phải là (H, W, 3) uint8, nhận {src.shape}")

    if mode == "jpeg_q95":
        ok, buf = cv2.imencode(".jpg", cv2.cvtColor(src, cv2.COLOR_RGB2BGR),
                               [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise RuntimeError("Nén JPEG thất bại")
        out = cv2.cvtColor(cv2.imdecode(buf, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        changed = int(np.count_nonzero(out != src))
        return np.ascontiguousarray(out), (
            f"Đã nén JPEG Q=95 ({len(buf):,} byte): {changed:,} giá trị kênh bị thay đổi → "
            "các bit LSB (Header HCST + CRC-16 + payload) bị phá hủy do nén có tổn hao.")

    out = src.copy()
    flat = out.reshape(-1)
    if mode == "flip_header_bit":
        flat[HEADER_TAMPER_BIT] ^= 1
        byte_i, bit_i = divmod(HEADER_TAMPER_BIT, 8)
        return out, (f"Đã đảo 1 bit LSB tại flat[{HEADER_TAMPER_BIT}] (byte {byte_i}, bit {bit_i} "
                     "của Header — trường ciphertext_len). Magic “HCST” còn nguyên nhưng CRC-16 "
                     "phải phát hiện metadata bị giả mạo.")
    if mode == "flip_payload_bits":
        info = inspect_stego_header(src)
        end = flat.size
        if info.is_valid and info.ciphertext_len is not None and info.num_lsb:
            end = min(flat.size, HEADER_BITS + math.ceil(8 * info.ciphertext_len / info.num_lsb))
        region = end - HEADER_BITS
        if region <= 0:
            raise ValueError("Ảnh không có vùng payload để đảo bit.")
        n = max(1, int(round(region * PAYLOAD_FLIP_FRACTION)))
        rng = np.random.default_rng(TAMPER_SEED)
        idx = HEADER_BITS + rng.choice(region, size=n, replace=False)
        flat[idx] ^= 1
        return out, (f"Đã đảo {n:,} bit LSB ({PAYLOAD_FLIP_FRACTION:.0%} vùng payload "
                     f"flat[{HEADER_BITS}:{end}]); Header 16-byte giữ nguyên nên vẫn qua kiểm tra "
                     "CRC, nhưng bản mã đã sai → CBC lan lỗi / ảnh khôi phục bị nhiễu.")
    if mode == "gaussian_noise":
        rng = np.random.default_rng(TAMPER_SEED)
        noisy = src.astype(np.float64) + rng.normal(0.0, GAUSSIAN_SIGMA, size=src.shape)
        out = np.clip(np.rint(noisy), 0, 255).astype(np.uint8)
        changed = int(np.count_nonzero(out != src))
        return out, (f"Đã cộng nhiễu Gaussian σ = {GAUSSIAN_SIGMA} (seed {TAMPER_SEED}): "
                     f"{changed:,} giá trị kênh thay đổi → kênh giấu tin LSB vốn mong manh "
                     "(fragile) bị phá vỡ.")
    raise ValueError(f"Chế độ tấn công không hỗ trợ: {mode!r} (chọn {', '.join(TAMPER_MODES)})")


simulate_attack = simulate_tamper


# ---------------------------------------------------------------- compare 3 ciphers
COMPARE_COLUMNS: tuple[str, ...] = (
    "Thuật toán", "num_lsb", "Cover Used", "MSE", "PSNR (dB)", "SSIM", "EncTime (µs)",
    "Tăng tốc so với 3DES (×)", "NPCR_enc (%)", "UACI_enc (%)", "Corr_enc", "Entropy_stego",
    "Entropy_enc", "Khôi phục (MSE=0)",
)


@dataclass
class CompareWorkflowResult:
    results: dict[str, EncryptWorkflowResult]
    table: pd.DataFrame
    cover_rgb: np.ndarray
    secret_gray: np.ndarray
    key_mode: str

    def panels(self) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        return {n: (r.encrypted_view, r.stego_rgb) for n, r in self.results.items()}

    def enc_times(self) -> dict[str, float]:
        return {n: r.enc_time_s for n, r in self.results.items()}

    def recovered(self) -> dict[str, np.ndarray]:
        return {n: r.recovered for n, r in self.results.items()}

    def metrics_frame(self) -> pd.DataFrame:
        rows = []
        for n, r in self.results.items():
            row: dict[str, Any] = {"cipher": n, "secret_h": r.secret_gray.shape[0],
                                   "secret_w": r.secret_gray.shape[1],
                                   "cover_used_h": r.cover_used_rgb.shape[0],
                                   "cover_used_w": r.cover_used_rgb.shape[1],
                                   "num_lsb": r.num_lsb, "was_scaled_up": r.was_scaled_up,
                                   "exact_recovery": r.is_exact, "key_mode": r.key_mode}
            row.update(r.metrics)
            rows.append(row)
        return pd.DataFrame(rows)


def build_compare_table(results: Mapping[str, EncryptWorkflowResult]) -> pd.DataFrame:
    ref = results["3des"].enc_time_s if "3des" in results else None
    rows = []
    for name, r in results.items():
        m = r.metrics
        h, w = r.cover_used_rgb.shape[:2]
        rows.append({
            "Thuật toán": CIPHER_LABELS[name],
            "num_lsb": r.num_lsb,
            "Cover Used": f"{h}×{w}" + (" (scaled)" if r.was_scaled_up else ""),
            "MSE": m["mse"],
            "PSNR (dB)": m["psnr"],
            "SSIM": m["ssim"],
            "EncTime (µs)": r.enc_time_s * 1e6,
            "Tăng tốc so với 3DES (×)": (ref / r.enc_time_s) if ref and r.enc_time_s > 0 else float("nan"),
            "NPCR_enc (%)": m["npcr_enc"],
            "UACI_enc (%)": m["uaci_enc"],
            "Corr_enc": m["corr_enc"],
            "Entropy_stego": m["entropy_stego"],
            "Entropy_enc": m["entropy_enc"],
            "Khôi phục (MSE=0)": "✅" if r.is_exact else "❌",
        })
    return pd.DataFrame(rows, columns=list(COMPARE_COLUMNS))


def run_compare_workflow(
    cover_rgb: np.ndarray,
    secret_gray: np.ndarray,
    cfg: dict[str, Any],
    *,
    ciphers: Iterable[str] = CIPHER_ORDER,
    key_mode: str = KEY_MODE_PAPER,
    passphrase: str | None = None,
    cache_chaotic_mask: bool = True,
    normalize: bool = True,
    secret_size: tuple[int, int] | None = None,
    progress: Callable[[str], None] | None = None,
) -> CompareWorkflowResult:
    """Run the three ciphers one after another on the same cover/secret pair."""
    cover = normalize_cover(cover_rgb, cfg) if normalize else np.ascontiguousarray(cover_rgb)
    secret = resize_secret(secret_gray, secret_size)
    results: dict[str, EncryptWorkflowResult] = {}
    for name in ciphers:
        canonical = canonical_cipher_name(name)
        if progress is not None:
            progress(canonical)
        results[canonical] = run_encrypt_workflow(
            cover, secret, cfg, cipher_name=canonical, key_mode=key_mode, passphrase=passphrase,
            cache_chaotic_mask=cache_chaotic_mask and canonical == "chaotic",
            normalize=False, secret_size=None)
    return CompareWorkflowResult(results=results, table=build_compare_table(results),
                                 cover_rgb=cover, secret_gray=secret, key_mode=key_mode)


def export_compare_bundle(result: CompareWorkflowResult, out_dir: str | Path) -> list[Path]:
    """Write Figure 4, Figure 5, the comparison CSV and per-cipher PNGs to ``out_dir``."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    from src.ui import plots

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    fig4 = plots.new_figure((9.5, 7.5))
    FigureCanvasAgg(fig4)
    plots.draw_figure4(fig4, result.cover_rgb, result.secret_gray)
    fig4.savefig(out / "fig4_cover_secret_histograms.png", dpi=150)
    written.append(out / "fig4_cover_secret_histograms.png")
    fig5 = plots.new_figure((12, 9.5))
    FigureCanvasAgg(fig5)
    plots.draw_figure5(fig5, result.panels())
    fig5.savefig(out / "fig5_comparison_grid.png", dpi=150)
    written.append(out / "fig5_comparison_grid.png")
    result.metrics_frame().to_csv(out / "compare_metrics.csv", index=False)
    written.append(out / "compare_metrics.csv")
    written.append(save_stego_png(out / "cover.png", result.cover_rgb))
    written.append(save_gray_png(out / "secret.png", result.secret_gray))
    for name, r in result.results.items():
        written.append(save_stego_png(out / f"{name}_stego.png", r.stego_rgb))
        written.append(save_gray_png(out / f"{name}_encrypted.png", r.encrypted_view))
        written.append(save_gray_png(out / f"{name}_recovered.png", r.recovered))
    return written


# -------------------------------------------------------------------- benchmark
SUMMARY_CSV = "benchmark_summary_table2.csv"
DETAILS_CSV = "benchmark_results.csv"


@dataclass
class BenchmarkBundle:
    summary: pd.DataFrame
    details: pd.DataFrame | None
    summary_path: Path
    details_path: Path | None
    paper_reference: dict[str, dict[str, float]] = field(
        default_factory=lambda: {k: dict(v) for k, v in PAPER_TABLE2_REFERENCE.items()})

    @property
    def ciphers(self) -> list[str]:
        return [str(c) for c in self.summary["cipher"]]

    def ours(self, details: pd.DataFrame | None = None) -> dict[str, dict[str, float]]:
        """Per-cipher averages: from (filtered) details when given, else from the summary."""
        if details is not None and not details.empty:
            out = {}
            for name, sub in details.groupby("cipher", sort=False):
                out[str(name)] = {k: float(sub[k].mean()) for k, _ in TABLE2_METRICS if k in sub}
            return out
        out = {}
        for _, row in self.summary.iterrows():
            out[str(row["cipher"])] = {k: float(row[f"avg_{k}"]) for k, _ in TABLE2_METRICS
                                       if f"avg_{k}" in row}
        return out

    def comparison_table(self, details: pd.DataFrame | None = None) -> pd.DataFrame:
        ours = self.ours(details)
        rows = []
        for name in [c for c in CIPHER_ORDER if c in ours]:
            for key, label in TABLE2_METRICS:
                mine = ours[name].get(key, float("nan"))
                paper = self.paper_reference.get(name, {}).get(key, float("nan"))
                rows.append({"cipher": name, "metric": key, "label": label, "ours": mine,
                             "paper": paper, "delta": mine - paper})
        return pd.DataFrame(rows)

    def filter_details(self, split: str | None = None, class_name: str | None = None) -> pd.DataFrame:
        if self.details is None:
            return pd.DataFrame()
        df = self.details
        if split and split != "all":
            df = df[df["split"] == split]
        if class_name and class_name != "all":
            df = df[df["class_name"] == class_name]
        return df

    def overview(self) -> dict[str, Any]:
        n_images = int(self.summary["n_images"].max()) if "n_images" in self.summary else 0
        runs = int(self.summary["n_images"].sum()) if "n_images" in self.summary else 0
        exact = float(self.summary["exact_recovery_rate"].min()) \
            if "exact_recovery_rate" in self.summary else float("nan")
        config = "—"
        if self.details is not None and not self.details.empty:
            n_images = int(self.details["image_index"].nunique())
            runs = int(len(self.details))
            exact = float(self.details["exact_recovery"].mean())
            h = int(self.details["secret_h"].mode().iloc[0])
            w = int(self.details["secret_w"].mode().iloc[0])
            k = int(self.details["num_lsb"].mode().iloc[0])
            config = f"{h}×{w} ({k}-LSB)"
        return {"n_images": n_images, "n_runs": runs, "exact_rate": exact, "config": config}


def load_benchmark_bundle(
    results_dir: str | Path | None = None,
    *,
    summary_path: str | Path | None = None,
    details_path: str | Path | None = None,
) -> BenchmarkBundle:
    """Load the Table 2 summary (required) and the per-image CSV (optional)."""
    from src.ui.resources import get_resource_root

    base = Path(results_dir) if results_dir is not None else get_resource_root() / "results"
    s_path = Path(summary_path) if summary_path is not None else base / SUMMARY_CSV
    if not s_path.is_file():
        raise FileNotFoundError(f"không tìm thấy file tổng hợp: {s_path}")
    summary = pd.read_csv(s_path)
    if "cipher" not in summary.columns:
        raise ValueError(f"{s_path.name} thiếu cột 'cipher' — không phải file tổng hợp Bảng 2")
    summary["cipher"] = summary["cipher"].astype(str).str.lower()

    d_path = Path(details_path) if details_path is not None else s_path.parent / DETAILS_CSV
    details = None
    if d_path.is_file():
        details = pd.read_csv(d_path)
        details["cipher"] = details["cipher"].astype(str).str.lower()
    else:
        d_path = None
    return BenchmarkBundle(summary=summary, details=details, summary_path=s_path,
                           details_path=d_path)


# ------------------------------------------------------------------------ formatting
def fmt_num(value: Any, digits: int = 4) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(v):
        return "—"
    if math.isinf(v):
        return "∞"
    if v != 0 and (abs(v) < 1e-3 or abs(v) >= 1e6):
        return f"{v:.3e}"
    return f"{v:,.{digits}f}"


def fmt_time_us(seconds: float) -> str:
    return f"{seconds * 1e6:,.1f} µs"


def guess_cipher_from_filename(path: str | Path) -> str | None:
    stem = Path(path).stem.lower()
    for name in ("3des", "des3", "aes", "chaotic"):
        if stem.startswith(name + "_") or stem == name:
            return _ALIASES[name]
    return None
