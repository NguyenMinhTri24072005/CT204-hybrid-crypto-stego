"""Vectorized multi-LSB steganography with a self-describing 16-byte header.

Layout on the C-order flattened channel array ``flat = cover.reshape(-1)`` (BM-02, BM-06):

    flat[0:128]           header (16 B = 128 bits), always at 1 LSB
    flat[128:128+N_used]  ciphertext bits, num_lsb ∈ {1..max_lsb} bits per channel value
    flat[128+N_used:]     untouched

Header (big-endian ``>4sBBHHIH``): magic b"HCST", version 1, num_lsb, secret_h, secret_w,
ciphertext_len, crc16 = zlib.crc32(header[:14]) & 0xFFFF.

num_lsb is the smallest k with 8·len(ct) <= (M-128)·k; beyond max_lsb the cover is scaled
up isotropically with cv2 (BM-07) and ``cover_used_rgb`` is returned for MSE/PSNR/SSIM.

All bit manipulation is NumPy-vectorized: there are no Python loops over pixels or bits.
"""

from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass

import cv2
import numpy as np

MAGIC = b"HCST"
VERSION = 1
HEADER_STRUCT = struct.Struct(">4sBBHHIH")
_HEADER_BODY = struct.Struct(">4sBBHHI")  # first 14 bytes, covered by the CRC
HEADER_BYTES = HEADER_STRUCT.size  # 16
HEADER_BITS = HEADER_BYTES * 8  # 128
MAX_SUPPORTED_LSB = 8

INTERPOLATIONS = {
    "nearest": cv2.INTER_NEAREST,
    "linear": cv2.INTER_LINEAR,
    "cubic": cv2.INTER_CUBIC,
    "area": cv2.INTER_AREA,
    "lanczos": cv2.INTER_LANCZOS4,
}


@dataclass(frozen=True)
class EmbedResult:
    stego_rgb: np.ndarray  # (H'_c, W'_c, 3) uint8 stego image
    cover_used_rgb: np.ndarray  # same shape as stego_rgb: reference for MSE/PSNR/SSIM (BM-07)
    num_lsb: int  # LSBs actually used for the payload (1..max_lsb)
    secret_shape: tuple[int, int]
    ciphertext_len: int
    was_scaled_up: bool


# --------------------------------------------------------------------------- header
def pack_header(num_lsb: int, secret_shape: tuple[int, int], ciphertext_len: int) -> bytes:
    """Serialize the 16-byte header (magic, version, num_lsb, H_s, W_s, length, CRC16)."""
    h, w = int(secret_shape[0]), int(secret_shape[1])
    if not 1 <= num_lsb <= MAX_SUPPORTED_LSB:
        raise ValueError(f"num_lsb must be in 1..{MAX_SUPPORTED_LSB}, got {num_lsb}")
    if not (1 <= h <= 0xFFFF and 1 <= w <= 0xFFFF):
        raise ValueError(f"secret_shape must be within 1..65535, got {secret_shape}")
    if not 0 <= ciphertext_len <= 0xFFFFFFFF:
        raise ValueError(f"ciphertext_len out of range: {ciphertext_len}")
    body = _HEADER_BODY.pack(MAGIC, VERSION, num_lsb, h, w, ciphertext_len)
    return body + struct.pack(">H", zlib.crc32(body) & 0xFFFF)


def unpack_header(header: bytes) -> tuple[int, tuple[int, int], int]:
    """Parse and validate a header; returns ``(num_lsb, (H_s, W_s), ciphertext_len)``."""
    if len(header) != HEADER_BYTES:
        raise ValueError(f"header must be {HEADER_BYTES} bytes, got {len(header)}")
    magic, version, num_lsb, h, w, ct_len, crc = HEADER_STRUCT.unpack(header)
    if magic != MAGIC:
        raise ValueError(f"bad magic {magic!r}: image carries no HCST payload")
    if crc != zlib.crc32(header[:14]) & 0xFFFF:
        raise ValueError("header CRC16 mismatch: stego image corrupted")
    if version != VERSION:
        raise ValueError(f"unsupported header version {version}")
    if not 1 <= num_lsb <= MAX_SUPPORTED_LSB:
        raise ValueError(f"invalid num_lsb {num_lsb} in header")
    if h == 0 or w == 0:
        raise ValueError(f"invalid secret shape {(h, w)} in header")
    return num_lsb, (h, w), ct_len


# ----------------------------------------------------------------------- bit helpers
def _bytes_to_bits(data: bytes) -> np.ndarray:
    """MSB-first bit array (uint8 0/1)."""
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def _write_lsb(values: np.ndarray, bits: np.ndarray, k: int) -> np.ndarray:
    """Write ``bits`` into the k low bits of ``values`` (one group of k bits per value)."""
    n = values.size
    groups = np.zeros(n * k, dtype=np.uint8)
    groups[: bits.size] = bits  # zero-pad the last group (<= k-1 bits)
    weights = (1 << np.arange(k - 1, -1, -1)).astype(np.uint8)  # MSB-first within a group
    symbols = (groups.reshape(n, k) * weights).sum(axis=1, dtype=np.uint16).astype(np.uint8)
    keep = np.uint8(0xFF ^ ((1 << k) - 1))
    return (values & keep) | symbols


def _read_lsb(values: np.ndarray, k: int, n_bits: int) -> np.ndarray:
    """Inverse of ``_write_lsb``: first ``n_bits`` bits stored in the k low bits."""
    shifts = np.arange(k - 1, -1, -1, dtype=np.uint8)
    bits = (values[:, None] >> shifts) & np.uint8(1)
    return bits.reshape(-1)[:n_bits]


# ------------------------------------------------------------------------- capacity
def payload_capacity_bits(num_channels: int, num_lsb: int) -> int:
    """Payload bits available after the 128-channel header region."""
    return max(num_channels - HEADER_BITS, 0) * num_lsb


def choose_num_lsb(num_channels: int, payload_bits: int, max_lsb: int) -> int | None:
    """Smallest k in 1..max_lsb that fits the payload, or None if it needs a scale-up."""
    ks = np.arange(1, max_lsb + 1)
    fits = payload_bits <= max(num_channels - HEADER_BITS, 0) * ks
    return int(ks[np.argmax(fits)]) if fits.any() else None


def scaled_cover_size(h: int, w: int, payload_bits: int, max_lsb: int) -> tuple[int, int]:
    """Minimal isotropic up-scaling so the payload fits at ``max_lsb`` (BM-07)."""
    m_req = math.ceil(payload_bits / max_lsb) + HEADER_BITS
    s = math.sqrt(m_req / (h * w * 3))
    new_h, new_w = math.ceil(h * s), math.ceil(w * s)
    if 3 * new_h * new_w < m_req:  # guard against float rounding
        if new_h <= new_w:
            new_h += 1
        else:
            new_w += 1
    if 3 * new_h * new_w < m_req:
        raise RuntimeError("scale-up size computation failed")
    return new_h, new_w


# ----------------------------------------------------------------------- public API
def embed(
    cover_rgb: np.ndarray,
    ciphertext: bytes,
    secret_shape: tuple[int, int],
    *,
    max_lsb: int = 3,
    interpolation: str = "cubic",
) -> EmbedResult:
    """Hide ``ciphertext`` (plus header) in ``cover_rgb``; never modifies the input."""
    cover = np.asarray(cover_rgb)
    if cover.dtype != np.uint8 or cover.ndim != 3 or cover.shape[2] != 3:
        raise ValueError(f"cover must be (H, W, 3) uint8, got {cover.shape} {cover.dtype}")
    if not 1 <= max_lsb <= MAX_SUPPORTED_LSB:
        raise ValueError(f"max_lsb must be in 1..{MAX_SUPPORTED_LSB}, got {max_lsb}")
    interp = INTERPOLATIONS.get(str(interpolation).lower())
    if interp is None:
        raise ValueError(f"unknown interpolation {interpolation!r}; use {sorted(INTERPOLATIONS)}")

    ct_len = len(ciphertext)
    payload_bits = 8 * ct_len
    h_c, w_c = cover.shape[:2]

    num_lsb = choose_num_lsb(cover.size, payload_bits, max_lsb)
    if num_lsb is None:
        num_lsb = max_lsb
        new_h, new_w = scaled_cover_size(h_c, w_c, payload_bits, max_lsb)
        cover_used = cv2.resize(cover, (new_w, new_h), interpolation=interp)
        was_scaled_up = True
    else:
        cover_used = cover.copy()
        was_scaled_up = False
    cover_used = np.ascontiguousarray(cover_used, dtype=np.uint8)

    header = pack_header(num_lsb, secret_shape, ct_len)
    stego = cover_used.copy()
    flat = stego.reshape(-1)  # view (C-contiguous)
    flat[:HEADER_BITS] = _write_lsb(flat[:HEADER_BITS], _bytes_to_bits(header), 1)

    n_used = math.ceil(payload_bits / num_lsb)
    if n_used:
        region = flat[HEADER_BITS : HEADER_BITS + n_used]
        flat[HEADER_BITS : HEADER_BITS + n_used] = _write_lsb(
            region, _bytes_to_bits(ciphertext), num_lsb
        )

    return EmbedResult(
        stego_rgb=stego,
        cover_used_rgb=cover_used,
        num_lsb=num_lsb,
        secret_shape=(int(secret_shape[0]), int(secret_shape[1])),
        ciphertext_len=ct_len,
        was_scaled_up=was_scaled_up,
    )


def extract(stego_rgb: np.ndarray) -> tuple[bytes, tuple[int, int], int]:
    """Blind extraction: returns ``(ciphertext, secret_shape, num_lsb)`` from the image alone.

    Raises ValueError for images smaller than 128 channel values, a wrong magic, a CRC16
    mismatch, or a header whose payload would run past the end of the image.
    """
    stego = np.asarray(stego_rgb)
    if stego.dtype != np.uint8:
        raise ValueError(f"stego image must be uint8, got {stego.dtype}")
    flat = np.ascontiguousarray(stego).reshape(-1)
    if flat.size < HEADER_BITS:
        raise ValueError(f"image has {flat.size} channel values, fewer than {HEADER_BITS}")

    header = np.packbits(_read_lsb(flat[:HEADER_BITS], 1, HEADER_BITS)).tobytes()
    num_lsb, secret_shape, ct_len = unpack_header(header)

    payload_bits = 8 * ct_len
    n_used = math.ceil(payload_bits / num_lsb)
    if HEADER_BITS + n_used > flat.size:
        raise ValueError(
            f"header declares {ct_len} bytes at {num_lsb} LSB, exceeding image capacity"
        )
    bits = _read_lsb(flat[HEADER_BITS : HEADER_BITS + n_used], num_lsb, payload_bits)
    return np.packbits(bits).tobytes(), secret_shape, num_lsb
