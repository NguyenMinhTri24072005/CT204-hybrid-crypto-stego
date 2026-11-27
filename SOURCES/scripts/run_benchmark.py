"""Batch benchmark over the Linnaeus 5 dataset (8,000 images x 3 ciphers) reproducing Table 2.

Usage (from ``SOURCES/``):
    .\\.venv\\Scripts\\python.exe -m scripts.run_benchmark --limit 10 --secret-size 156 156
    .\\.venv\\Scripts\\python.exe -m scripts.run_benchmark --secret-size 156 156
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

from src.config import load_config
from src.crypto import BaseCipher, create_cipher
from src.pipeline import ensure_secret_gray, read_rgb, run_pipeline

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def discover_dataset_images(data_dir: Path, splits: list[str]) -> list[tuple[str, str, Path]]:
    """Return deterministically sorted ``(split, class_name, image_path)`` entries."""
    entries: list[tuple[str, str, Path]] = []
    for split in splits:
        split_dir = data_dir / split
        if not split_dir.is_dir():
            continue
        for class_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
            files = sorted(
                (
                    f
                    for f in class_dir.iterdir()
                    if f.is_file() and f.suffix.lower() in _IMAGE_SUFFIXES
                ),
                key=lambda f: f.name,
            )
            for img_path in files:
                entries.append((split, class_dir.name, img_path))
    if not entries:
        raise FileNotFoundError(
            f"no dataset images found in {data_dir} for splits={splits}"
        )
    return entries


def summary_csv_name(csv_name: str) -> str:
    """``benchmark_results.csv`` -> ``benchmark_summary_table2.csv`` (spec §3.3.3)."""
    stem = Path(csv_name).stem
    stem = stem[: -len("_results")] if stem.endswith("_results") else stem
    return f"{stem}_summary_table2.csv"


def build_summary_dataframe(df: pd.DataFrame, cipher_order: list[str]) -> pd.DataFrame:
    """Aggregate per-cipher averages and standard deviations aligned with Paper Table 2."""
    summary_rows: list[dict[str, Any]] = []
    for cipher_name in cipher_order:
        sub = df[df["cipher"] == cipher_name]
        if sub.empty:
            continue
        summary_rows.append(
            {
                "cipher": cipher_name,
                "n_images": int(len(sub)),
                "exact_recovery_rate": float(sub["exact_recovery"].mean()),
                "avg_mse": float(sub["mse"].mean()),
                "avg_psnr": float(sub["psnr"].mean()),
                "avg_ssim": float(sub["ssim"].mean()),
                "avg_enc_time_s": float(sub["enc_time_s"].mean()),
                "avg_npcr_enc": float(sub["npcr_enc"].mean()),
                "avg_uaci_enc": float(sub["uaci_enc"].mean()),
                "avg_corr_enc": float(sub["corr_enc"].mean()),
                "avg_entropy_stego": float(sub["entropy_stego"].mean()),
                "avg_entropy_enc": float(sub["entropy_enc"].mean()),
                "avg_npcr_stego": float(sub["npcr_stego"].mean()),
                "avg_uaci_stego": float(sub["uaci_stego"].mean()),
                "avg_corr_stego": float(sub["corr_stego"].mean()),
                "std_mse": float(sub["mse"].std(ddof=0)),
                "std_psnr": float(sub["psnr"].std(ddof=0)),
                "std_ssim": float(sub["ssim"].std(ddof=0)),
                "std_enc_time_s": float(sub["enc_time_s"].std(ddof=0)),
            }
        )
    return pd.DataFrame(summary_rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Linnaeus 5 batch benchmark across 3DES, AES, and Chaotic ciphers."
    )
    parser.add_argument("--config", type=Path, default=None, help="Path to YAML config file.")
    parser.add_argument("--data-dir", type=Path, default=None, help="Override Linnaeus 5 root directory.")
    parser.add_argument("--secret", type=Path, default=None, help="Override grayscale secret path.")
    parser.add_argument(
        "--secret-size",
        type=int,
        nargs=2,
        metavar=("H", "W"),
        default=None,
        help="Resize secret image to (H, W), e.g. --secret-size 156 156 for Table 2 1-LSB setup.",
    )
    parser.add_argument("--out-dir", type=Path, default=None, help="Override results output directory.")
    parser.add_argument("--csv-name", type=str, default=None, help="Override detailed CSV filename.")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N cover images.")
    parser.add_argument(
        "--vary-key-per-image",
        action="store_true",
        help="Derive a fresh deterministic key/IV/seed per image via seed_offset=image_index (BM-03).",
    )
    parser.add_argument(
        "--cache-chaotic-mask",
        action="store_true",
        help="Pre-cache chaotic+ECC keystream mask before timing (BM-10).",
    )
    parser.add_argument("--quiet", action="store_true", help="Disable tqdm progress bar and stdout summary.")
    return parser


def main(argv: list[str] | None = None) -> tuple[Path, Path]:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    stego_cfg = cfg["stego"]
    bench_cfg = cfg["benchmark"]

    data_dir = Path(args.data_dir) if args.data_dir is not None else Path(cfg["paths"]["data_dir"])
    out_dir = Path(args.out_dir) if args.out_dir is not None else Path(cfg["paths"]["results_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    secret_path = Path(args.secret) if args.secret is not None else Path(cfg["secret"]["path"])
    cfg_resize = cfg["secret"].get("resize")
    secret_size = (
        (int(args.secret_size[0]), int(args.secret_size[1]))
        if args.secret_size is not None
        else (tuple(cfg_resize) if cfg_resize else None)
    )
    secret_gray = ensure_secret_gray(secret_path, secret_size)

    cover_size = tuple(stego_cfg["cover_size"])
    max_lsb = int(stego_cfg["max_lsb"])
    interpolation = str(stego_cfg.get("scale_up_interpolation", "cubic"))
    cipher_names: list[str] = [str(c) for c in bench_cfg["ciphers"]]
    splits: list[str] = [str(s) for s in bench_cfg["splits"]]

    entries = discover_dataset_images(data_dir, splits)
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError(f"--limit must be positive, got {args.limit}")
        entries = entries[: args.limit]

    # Warm up all ciphers once up front so Numba JIT compile cost is excluded (BM-10).
    static_ciphers: dict[str, BaseCipher] = {}
    for name in cipher_names:
        c = create_cipher(name, cfg, cache_chaotic_mask=args.cache_chaotic_mask)
        c.warmup()
        if args.cache_chaotic_mask and c.name == "chaotic":
            c.encrypt(b"\x00" * secret_gray.size)
        static_ciphers[name] = c

    rows: list[dict[str, Any]] = []
    iterator = tqdm(entries, desc="Linnaeus-5 Benchmark", disable=args.quiet)
    for img_idx, (split, class_name, img_path) in enumerate(iterator):
        cover_rgb = read_rgb(img_path, size=cover_size)
        for name in cipher_names:
            if args.vary_key_per_image:
                cipher = create_cipher(
                    name,
                    cfg,
                    seed_offset=img_idx,
                    cache_chaotic_mask=args.cache_chaotic_mask,
                )
                if args.cache_chaotic_mask and cipher.name == "chaotic":
                    cipher.encrypt(b"\x00" * secret_gray.size)
            else:
                cipher = static_ciphers[name]

            res = run_pipeline(
                secret_gray,
                cover_rgb,
                cipher,
                max_lsb=max_lsb,
                interpolation=interpolation,
                stego_path=None,
                compute_metrics=True,
                warmup=False,
            )
            if not res.is_exact:
                raise RuntimeError(
                    f"lossless recovery failed on image {img_path} with cipher {cipher.name}"
                )

            row: dict[str, Any] = {
                "image_index": img_idx,
                "split": split,
                "class_name": class_name,
                "image_name": img_path.name,
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

    df = pd.DataFrame(rows)
    csv_name = args.csv_name or str(bench_cfg.get("csv_name", "benchmark_results.csv"))
    detailed_csv = out_dir / csv_name
    df.to_csv(detailed_csv, index=False)

    canonical_order = [static_ciphers[n].name for n in cipher_names]
    summary_df = build_summary_dataframe(df, canonical_order)
    summary_csv = out_dir / summary_csv_name(csv_name)
    summary_df.to_csv(summary_csv, index=False)

    if not args.quiet:
        table2_cols = [
            "cipher",
            "n_images",
            "avg_mse",
            "avg_psnr",
            "avg_ssim",
            "avg_enc_time_s",
            "avg_npcr_enc",
            "avg_uaci_enc",
            "avg_corr_enc",
            "avg_entropy_stego",
            "avg_entropy_enc",
        ]
        print(f"\n[run_benchmark] Detailed CSV: {detailed_csv}")
        print(f"[run_benchmark] Summary CSV : {summary_csv}\n")
        print(summary_df[table2_cols].to_string(index=False))

    return detailed_csv, summary_csv


if __name__ == "__main__":
    main()
