"""Cryptographic security, differential, entropy, correlation, and speed metrics.

Paper references (Docs/145987.md §4.4.2–4.4.6, Eq. 6–8) & ADR decisions:
- BM-08: expose generic functions and compute dual metric groups:
    * ``*_enc``   measured on ``secret_gray`` vs ``encrypted_view_gray``
    * ``*_stego`` measured on ``cover_used_rgb`` vs ``stego_rgb`` (and ``stego_rgb`` entropy)
- BM-09: ``cross_correlation`` computes flat Pearson r for 2D images and channel-averaged
  Pearson r across R, G, B for 3D images ("mean RGB channel correlation").
- BM-10: ``measure_enc_time`` warms up ``cipher`` beforehand (excluding Numba JIT compile
  cost) and times strictly ``cipher.encrypt(plaintext)`` via ``time.perf_counter()``.
"""

from __future__ import annotations

import math
import time

import numpy as np

from src.crypto.base import BaseCipher
from src.metrics.visual import validate_image_pair

_DIRECTIONS = ("horizontal", "vertical", "diagonal")


def _validate_single_image(img: np.ndarray) -> np.ndarray:
    arr = np.asarray(img)
    if arr.dtype != np.uint8:
        raise ValueError(f"image must be uint8, got {arr.dtype}")
    if arr.ndim not in (2, 3) or arr.size == 0:
        raise ValueError(f"image must be a non-empty 2D or 3D array, got shape {arr.shape}")
    return arr


def measure_enc_time(
    cipher: BaseCipher,
    plaintext: bytes,
    *,
    warmup: bool = True,
) -> tuple[bytes, float]:
    """Time strictly ``cipher.encrypt(plaintext)`` in seconds (BM-10).

    With ``warmup=True`` the Numba JIT is compiled first and, for a ChaoticCipher built with
    ``cache_mask=True``, the keystream for ``len(plaintext)`` is precomputed so that only the
    XOR is timed (the documented meaning of the cached mode). Both steps are outside the timer.
    """
    if warmup:
        cipher.warmup()
        if getattr(cipher, "cache_mask", False):
            cipher.combined_mask(len(plaintext))
    t0 = time.perf_counter()
    ciphertext = cipher.encrypt(plaintext)
    elapsed = time.perf_counter() - t0
    return ciphertext, float(elapsed)


def npcr(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """Number of Pixels Change Rate in percent [0, 100] (Eq. 6)."""
    a, b = validate_image_pair(img_a, img_b)
    return float(np.count_nonzero(a != b) / a.size * 100.0)


def uaci(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """Unified Average Changing Intensity in percent [0, 100] (Eq. 7, float64 safe)."""
    a, b = validate_image_pair(img_a, img_b)
    mean_abs = float(np.mean(np.abs(a.astype(np.float64) - b.astype(np.float64))))
    return float(mean_abs / 255.0 * 100.0)


def shannon_entropy(img: np.ndarray) -> float:
    """Shannon information entropy in bits/byte over 256 intensity bins [0, 8] (Eq. 8)."""
    arr = _validate_single_image(img)
    counts = np.bincount(arr.reshape(-1), minlength=256)
    nonzero = counts[counts > 0]
    probs = nonzero.astype(np.float64) / float(arr.size)
    return float(-np.sum(probs * np.log2(probs)))


def _pearson_1d(x: np.ndarray, y: np.ndarray) -> float:
    """Numerically safe Pearson correlation in [-1, 1]; returns 0.0 if variance is zero."""
    xf = x.astype(np.float64, copy=False).reshape(-1)
    yf = y.astype(np.float64, copy=False).reshape(-1)
    if xf.size < 2:
        return 0.0
    dx = xf - xf.mean()
    dy = yf - yf.mean()
    denom = math.sqrt(float(np.dot(dx, dx)) * float(np.dot(dy, dy)))
    if denom == 0.0:
        return 0.0
    r = float(np.dot(dx, dy)) / denom
    return max(-1.0, min(1.0, r))


def cross_correlation(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """Pearson correlation between two images (flat for 2D; mean per-channel for 3D, BM-09)."""
    a, b = validate_image_pair(img_a, img_b)
    if a.ndim == 2:
        return _pearson_1d(a, b)
    channels = a.shape[2]
    return float(sum(_pearson_1d(a[..., c], b[..., c]) for c in range(channels)) / channels)


def adjacent_pixel_correlation(img: np.ndarray, direction: str = "horizontal") -> float:
    """Correlation between adjacent pixel pairs along ``horizontal | vertical | diagonal``."""
    arr = _validate_single_image(img)
    kind = str(direction).strip().lower()
    if kind not in _DIRECTIONS:
        raise ValueError(f"direction must be one of {_DIRECTIONS}, got {direction!r}")
    if kind == "horizontal":
        x, y = arr[:, :-1], arr[:, 1:]
    elif kind == "vertical":
        x, y = arr[:-1, :], arr[1:, :]
    else:
        x, y = arr[:-1, :-1], arr[1:, 1:]
    if x.size == 0:
        return 0.0
    if arr.ndim == 2:
        return _pearson_1d(x, y)
    channels = arr.shape[2]
    return float(sum(_pearson_1d(x[..., c], y[..., c]) for c in range(channels)) / channels)


def compute_dual_security_metrics(
    secret_gray: np.ndarray,
    encrypted_view_gray: np.ndarray,
    cover_used_rgb: np.ndarray,
    stego_rgb: np.ndarray,
) -> dict[str, float]:
    """Compute both ``*_enc`` and ``*_stego`` security metric groups (BM-08)."""
    return {
        "npcr_enc": npcr(secret_gray, encrypted_view_gray),
        "uaci_enc": uaci(secret_gray, encrypted_view_gray),
        "corr_enc": cross_correlation(secret_gray, encrypted_view_gray),
        "entropy_enc": shannon_entropy(encrypted_view_gray),
        "npcr_stego": npcr(cover_used_rgb, stego_rgb),
        "uaci_stego": uaci(cover_used_rgb, stego_rgb),
        "corr_stego": cross_correlation(cover_used_rgb, stego_rgb),
        "entropy_stego": shannon_entropy(stego_rgb),
    }
