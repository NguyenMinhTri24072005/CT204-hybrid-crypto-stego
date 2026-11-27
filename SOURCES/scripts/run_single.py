"""Single-pair demo script reproducing Paper Figures 4 & 5 and saving images + metrics.

Usage (from ``SOURCES/``):
    .\\.venv\\Scripts\\python.exe -m scripts.run_single
    .\\.venv\\Scripts\\python.exe -m scripts.run_single --secret-size 156 156
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import load_config
from src.crypto import create_cipher
from src.pipeline import (
    PipelineResult,
    ensure_secret_gray,
    read_rgb,
    run_pipeline,
    save_gray_png,
    save_stego_png,
)

_HIST_COLOR = "#1f3b4d"
_TITLES = {
    "3des": "3DES-LSB\nSteganography",
    "aes": "AES-LSB\nSteganography",
    "chaotic": "Chaotic + PRNG Masking\nSteganography",
}


def _ensure_cover(cover_path: Path, cfg: dict[str, Any], cover_size: tuple[int, int]) -> np.ndarray:
    """Load RGB cover; fall back to first Linnaeus 5 image if sample cover is absent."""
    if cover_path.is_file():
        return read_rgb(cover_path, size=cover_size)
    data_dir = Path(cfg["paths"]["data_dir"])
    candidates = sorted(data_dir.glob("*/*/*.jpg"))
    if candidates:
        return read_rgb(candidates[0], size=cover_size)
    raise FileNotFoundError(f"cover image not found at {cover_path} or under {data_dir}")


def _plot_pooled_histogram(ax: plt.Axes, img: np.ndarray, title: str) -> None:
    """Plot 256-bin intensity histogram over ``img.ravel()`` (BM-10, matches MATLAB Figure 4/5)."""
    counts = np.bincount(img.reshape(-1), minlength=256)
    ax.bar(np.arange(256), counts, width=1.0, color=_HIST_COLOR, edgecolor="none")
    ax.set_xlim(-0.5, 255.5)  # full width of the 0 and 255 bins
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.tick_params(labelsize=8)


def save_figure4(cover_rgb: np.ndarray, secret_gray: np.ndarray, out_path: Path) -> Path:
    """Reproduce Paper Figure 4: cover + secret images and their 256-bin histograms."""
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 7.5), constrained_layout=True)

    axes[0, 0].imshow(cover_rgb)
    axes[0, 0].set_title(f"Sample Cover Image ({cover_rgb.shape[0]}x{cover_rgb.shape[1]} RGB)", fontsize=10, fontweight="bold")
    axes[0, 0].axis("off")

    axes[0, 1].imshow(secret_gray, cmap="gray", vmin=0, vmax=255)
    axes[0, 1].set_title(f"Secret Image ({secret_gray.shape[0]}x{secret_gray.shape[1]} Gray)", fontsize=10, fontweight="bold")
    axes[0, 1].axis("off")

    _plot_pooled_histogram(axes[1, 0], cover_rgb, "Cover Histogram")
    _plot_pooled_histogram(axes[1, 1], secret_gray, "Histogram of Original Secret")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return out_path


def save_figure5(results: list[PipelineResult], out_path: Path) -> Path:
    """Reproduce Paper Figure 5: 3 rows (Encrypted, Encrypted Hist, Stego Hist) x 3 ciphers."""
    cols = len(results)
    fig, axes = plt.subplots(3, cols, figsize=(4.0 * cols, 9.5), constrained_layout=True)
    if cols == 1:
        axes = axes[:, None]

    for col, res in enumerate(results):
        header = _TITLES.get(res.cipher_name, res.cipher_name.upper())
        axes[0, col].imshow(res.encrypted_view, cmap="gray", vmin=0, vmax=255)
        axes[0, col].set_title(f"{header}\n\nEncrypted Secret Image", fontsize=10, fontweight="bold")
        axes[0, col].axis("off")

        _plot_pooled_histogram(axes[1, col], res.encrypted_view, "Histogram of Encrypted Secret")
        _plot_pooled_histogram(axes[2, col], res.stego_rgb, "Stego Histogram")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run single cover/secret pair across all 3 ciphers.")
    parser.add_argument("--config", type=Path, default=None, help="Path to YAML config file.")
    parser.add_argument("--cover", type=Path, default=None, help="Override RGB cover image path.")
    parser.add_argument("--secret", type=Path, default=None, help="Override grayscale secret path.")
    parser.add_argument(
        "--secret-size",
        type=int,
        nargs=2,
        metavar=("H", "W"),
        default=None,
        help="Resize secret image to (H, W), e.g. --secret-size 156 156 for Table 2 1-LSB setup.",
    )
    parser.add_argument("--out-dir", type=Path, default=None, help="Output directory (default: results/single).")
    parser.add_argument(
        "--cache-chaotic-mask",
        action="store_true",
        help="Pre-cache chaotic+ECC keystream mask before timing (BM-10).",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress console summary output.")
    return parser


def main(argv: list[str] | None = None) -> Path:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    stego_cfg = cfg["stego"]

    out_dir = Path(args.out_dir) if args.out_dir is not None else Path(cfg["paths"]["results_dir"]) / "single"
    out_dir.mkdir(parents=True, exist_ok=True)

    cover_path = Path(args.cover) if args.cover is not None else Path(cfg["paths"]["sample_dir"]) / "cover.jpg"
    secret_path = Path(args.secret) if args.secret is not None else Path(cfg["secret"]["path"])
    cfg_resize = cfg["secret"].get("resize")
    secret_size = (
        (int(args.secret_size[0]), int(args.secret_size[1]))
        if args.secret_size is not None
        else (tuple(cfg_resize) if cfg_resize else None)
    )

    cover_rgb = _ensure_cover(cover_path, cfg, tuple(stego_cfg["cover_size"]))
    secret_gray = ensure_secret_gray(secret_path, secret_size)

    save_stego_png(out_dir / "cover.png", cover_rgb)
    save_gray_png(out_dir / "secret.png", secret_gray)

    results: list[PipelineResult] = []
    rows: list[dict[str, Any]] = []

    for cipher_name in cfg["benchmark"]["ciphers"]:
        cipher = create_cipher(cipher_name, cfg, cache_chaotic_mask=args.cache_chaotic_mask)
        cipher.warmup()
        if args.cache_chaotic_mask and cipher.name == "chaotic":
            cipher.encrypt(b"\x00" * secret_gray.size)

        stego_path = out_dir / f"{cipher.name}_stego.png"
        res = run_pipeline(
            secret_gray,
            cover_rgb,
            cipher,
            max_lsb=int(stego_cfg["max_lsb"]),
            interpolation=str(stego_cfg.get("scale_up_interpolation", "cubic")),
            stego_path=stego_path,
            compute_metrics=True,
            warmup=False,
        )
        if not res.is_exact:
            raise RuntimeError(f"recovery failed (MSE != 0) for cipher {cipher.name}")

        save_gray_png(out_dir / f"{cipher.name}_encrypted.png", res.encrypted_view)
        save_gray_png(out_dir / f"{cipher.name}_recovered.png", res.recovered)
        results.append(res)

        row: dict[str, Any] = {
            "cipher": res.cipher_name,
            "secret_h": res.secret.shape[0],
            "secret_w": res.secret.shape[1],
            "cover_used_h": res.cover_used_rgb.shape[0],
            "cover_used_w": res.cover_used_rgb.shape[1],
            "num_lsb": res.embed.num_lsb,
            "was_scaled_up": res.embed.was_scaled_up,
            "exact_recovery": res.is_exact,
        }
        row.update(res.metrics)
        rows.append(row)

    save_figure4(cover_rgb, secret_gray, out_dir / "fig4_cover_secret_histograms.png")
    save_figure5(results, out_dir / "fig5_comparison_grid.png")

    df = pd.DataFrame(rows)
    csv_path = out_dir / "single_metrics.csv"
    df.to_csv(csv_path, index=False)

    if not args.quiet:
        display_cols = [
            "cipher",
            "num_lsb",
            "was_scaled_up",
            "mse",
            "psnr",
            "ssim",
            "enc_time_s",
            "npcr_enc",
            "uaci_enc",
            "corr_enc",
            "entropy_stego",
            "entropy_enc",
        ]
        print(f"\n[run_single] Saved figures and images to: {out_dir}")
        print(df[display_cols].to_string(index=False))

    return out_dir


if __name__ == "__main__":
    main()
