"""Visual quality metrics between the reference cover image and the stego image.

Paper references (Docs/145987.md §4.4.1, Eq. 3–5) & ADR decisions:
- BM-07: compare ``cover_used_rgb`` (same dimensions as ``stego_rgb``) against ``stego_rgb``.
- BM-09: for RGB images, MSE divides by ``H * W * 3`` (matching MATLAB ``immse``), so
  full 1-LSB embedding of uniform bits yields MSE ≈ 0.50 and PSNR ≈ 51.14 dB (Table 2).
"""

from __future__ import annotations

import math

import numpy as np
from skimage.metrics import structural_similarity


def validate_image_pair(img_a: np.ndarray, img_b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Validate two non-empty uint8 images (2D grayscale or 3D multi-channel) of equal shape."""
    a = np.asarray(img_a)
    b = np.asarray(img_b)
    if a.dtype != np.uint8 or b.dtype != np.uint8:
        raise ValueError(f"images must be uint8, got {a.dtype} and {b.dtype}")
    if a.shape != b.shape:
        raise ValueError(f"image shapes must match, got {a.shape} vs {b.shape}")
    if a.ndim not in (2, 3) or a.size == 0:
        raise ValueError(f"images must be non-empty 2D or 3D arrays, got shape {a.shape}")
    return a, b


def mse(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """Mean Squared Error over all array elements ``H * W (* C)`` in float64 (Eq. 3, BM-09)."""
    a, b = validate_image_pair(img_a, img_b)
    diff = a.astype(np.float64) - b.astype(np.float64)
    return float(np.mean(diff * diff))


def psnr(img_a: np.ndarray, img_b: np.ndarray, *, data_range: float = 255.0) -> float:
    """Peak Signal-to-Noise Ratio in dB (Eq. 4); returns ``inf`` when images are identical."""
    err = mse(img_a, img_b)
    if err == 0.0:
        return float("inf")
    return float(10.0 * math.log10((data_range * data_range) / err))


def ssim(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """Structural Similarity Index (Eq. 5) matching Wang et al. (2004) / MATLAB ``ssim`` (BM-09).

    Uses an 11x11 Gaussian window (``sigma=1.5``, ``use_sample_covariance=False``) for images
    at least 11x11; falls back to an odd uniform window when ``3 <= min(H, W) < 11``.
    """
    a, b = validate_image_pair(img_a, img_b)
    min_side = min(a.shape[0], a.shape[1])
    if min_side < 3:
        raise ValueError(f"SSIM requires spatial dimensions >= 3, got {a.shape[:2]}")
    channel_axis = -1 if a.ndim == 3 else None
    if min_side >= 11:
        return float(
            structural_similarity(
                a,
                b,
                data_range=255,
                channel_axis=channel_axis,
                gaussian_weights=True,
                sigma=1.5,
                use_sample_covariance=False,
            )
        )
    win_size = min_side if min_side % 2 == 1 else min_side - 1
    return float(
        structural_similarity(
            a,
            b,
            data_range=255,
            channel_axis=channel_axis,
            win_size=win_size,
        )
    )


def compute_visual_metrics(cover_used_rgb: np.ndarray, stego_rgb: np.ndarray) -> dict[str, float]:
    """Compute ``mse``, ``psnr``, and ``ssim`` in a single pass."""
    err = mse(cover_used_rgb, stego_rgb)
    peak = float("inf") if err == 0.0 else float(10.0 * math.log10((255.0 * 255.0) / err))
    return {
        "mse": err,
        "psnr": peak,
        "ssim": ssim(cover_used_rgb, stego_rgb),
    }
