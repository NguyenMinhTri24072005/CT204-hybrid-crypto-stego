"""Visual imperceptibility and cryptographic security evaluation metrics."""

from __future__ import annotations

import numpy as np

from src.metrics.security import (
    adjacent_pixel_correlation,
    compute_dual_security_metrics,
    cross_correlation,
    measure_enc_time,
    npcr,
    shannon_entropy,
    uaci,
)
from src.metrics.visual import compute_visual_metrics, mse, psnr, ssim, validate_image_pair


def compute_all_metrics(
    secret_gray: np.ndarray,
    encrypted_view_gray: np.ndarray,
    cover_used_rgb: np.ndarray,
    stego_rgb: np.ndarray,
    *,
    enc_time_s: float | None = None,
) -> dict[str, float]:
    """Combine visual metrics, dual security metrics, and optional ``enc_time_s``."""
    out = compute_visual_metrics(cover_used_rgb, stego_rgb)
    if enc_time_s is not None:
        out["enc_time_s"] = float(enc_time_s)
    out.update(
        compute_dual_security_metrics(
            secret_gray,
            encrypted_view_gray,
            cover_used_rgb,
            stego_rgb,
        )
    )
    return out


__all__ = [
    "adjacent_pixel_correlation",
    "compute_all_metrics",
    "compute_dual_security_metrics",
    "compute_visual_metrics",
    "cross_correlation",
    "measure_enc_time",
    "mse",
    "npcr",
    "psnr",
    "shannon_entropy",
    "ssim",
    "uaci",
    "validate_image_pair",
]
