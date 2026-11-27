"""Pure ``matplotlib.figure.Figure`` painters shared by the tabs and the exporters.

No ``pyplot`` and no backend switching: every function receives a ``Figure`` and draws on it,
so the same code renders inside Tk (``FigureCanvasTkAgg``) or saves to PNG (``savefig``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from src.ui.theme import CIPHER_COLORS, COLORS, HIST_COLOR, PAPER_COLOR

CIPHER_TITLES = {
    "3des": "3DES-LSB",
    "aes": "AES-LSB",
    "chaotic": "Chaotic + PRNG Masking",
}


def new_figure(figsize: tuple[float, float], dpi: int = 100) -> Figure:
    return Figure(figsize=figsize, dpi=dpi, facecolor="white")


def _style_axes(ax: Axes) -> None:
    ax.tick_params(labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def plot_hist256(ax: Axes, img: np.ndarray, title: str, *, color: str = HIST_COLOR) -> None:
    """256-bin histogram of ``img.ravel()`` (RGB channels pooled, BM-10)."""
    counts = np.bincount(np.asarray(img, dtype=np.uint8).reshape(-1), minlength=256)
    ax.bar(np.arange(256), counts, width=1.0, color=color, edgecolor="none")
    ax.set_xlim(-0.5, 255.5)
    ax.set_title(title, fontsize=9, fontweight="bold", color=COLORS["navy"])
    _style_axes(ax)


def draw_triple_histograms(fig: Figure, cover: np.ndarray, encrypted_view: np.ndarray,
                           stego: np.ndarray) -> None:
    axes = fig.subplots(1, 3)
    plot_hist256(axes[0], cover, "Cover Histogram")
    plot_hist256(axes[1], encrypted_view, "Encrypted Secret Histogram")
    plot_hist256(axes[2], stego, "Stego Histogram")
    fig.tight_layout()


def draw_figure4(fig: Figure, cover: np.ndarray, secret: np.ndarray) -> None:
    """Paper Figure 4: cover + secret and their 256-bin histograms."""
    axes = fig.subplots(2, 2)
    axes[0, 0].imshow(cover)
    axes[0, 0].set_title(f"Sample Cover Image ({cover.shape[0]}×{cover.shape[1]})", fontsize=9,
                         fontweight="bold")
    axes[0, 1].imshow(secret, cmap="gray", vmin=0, vmax=255)
    axes[0, 1].set_title(f"Secret Image ({secret.shape[0]}×{secret.shape[1]})", fontsize=9,
                         fontweight="bold")
    for ax in axes[0]:
        ax.axis("off")
    plot_hist256(axes[1, 0], cover, "Cover Histogram")
    plot_hist256(axes[1, 1], secret, "Histogram of Original Secret")
    fig.tight_layout()


def draw_figure5(fig: Figure, panels: Mapping[str, tuple[np.ndarray, np.ndarray]]) -> None:
    """Paper Figure 5: columns = ciphers; rows = encrypted image, its histogram, stego histogram.

    ``panels`` maps cipher name -> ``(encrypted_view, stego_rgb)``.
    """
    names = list(panels)
    axes = fig.subplots(3, len(names), squeeze=False)
    for col, name in enumerate(names):
        enc, stego = panels[name]
        title = CIPHER_TITLES.get(name, name.upper())
        axes[0, col].imshow(enc, cmap="gray", vmin=0, vmax=255, interpolation="nearest")
        axes[0, col].set_title(f"{title}\nEncrypted Secret Image", fontsize=9, fontweight="bold",
                               color=COLORS["navy"])
        axes[0, col].axis("off")
        plot_hist256(axes[1, col], enc, "Histogram of Encrypted Secret")
        plot_hist256(axes[2, col], stego, "Stego Histogram")
    fig.tight_layout()


def draw_speed_and_recovered(fig: Figure, enc_times_s: Mapping[str, float],
                             recovered: Mapping[str, np.ndarray]) -> None:
    """Horizontal EncTime bars (log µs, × faster vs 3DES) next to the recovered secrets."""
    names = list(enc_times_s)
    grid = fig.add_gridspec(len(names), 2, width_ratios=[1.6, 1.0])
    ax = fig.add_subplot(grid[:, 0])
    us = np.array([max(enc_times_s[n], 1e-9) * 1e6 for n in names])
    ref = enc_times_s.get("3des")
    y = np.arange(len(names))
    ax.barh(y, us, color=[CIPHER_COLORS.get(n, COLORS["blue"]) for n in names])
    ax.set_yticks(y, [CIPHER_TITLES.get(n, n) for n in names], fontsize=9)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlabel("EncTime (µs, thang log)", fontsize=9)
    ax.set_title("Tốc độ mã hóa", fontsize=10, fontweight="bold", color=COLORS["navy"])
    for i, n in enumerate(names):
        label = f"{us[i]:,.1f} µs"
        if ref:
            label += f"  (×{ref / max(enc_times_s[n], 1e-12):.1f})"
        ax.text(us[i], i, "  " + label, va="center", fontsize=8)
    ax.set_xlim(us.min() / 3, us.max() * 30)
    _style_axes(ax)
    for i, n in enumerate(names):
        rax = fig.add_subplot(grid[i, 1])
        img = recovered.get(n)
        if img is not None:
            rax.imshow(img, cmap="gray", vmin=0, vmax=255)
        rax.set_title(f"{CIPHER_TITLES.get(n, n)} — khôi phục", fontsize=8)
        rax.axis("off")
    fig.tight_layout()


# ----------------------------------------------------------------------- benchmark
_PAPER_VS_OURS_PANELS: Sequence[tuple[str, str, bool]] = (
    ("psnr", "PSNR (dB)", False),
    ("npcr_enc", "NPCR (%)", False),
    ("uaci_enc", "UACI (%)", False),
    ("enc_time_s", "EncTime (µs, log)", True),
)


def draw_paper_vs_ours(fig: Figure, ours: Mapping[str, Mapping[str, float]],
                       paper: Mapping[str, Mapping[str, float]]) -> None:
    """Grouped bars (ours vs paper Table 2) for PSNR, NPCR, UACI and EncTime (log)."""
    names = [n for n in ("3des", "aes", "chaotic") if n in ours]
    axes = fig.subplots(1, len(_PAPER_VS_OURS_PANELS))
    x = np.arange(len(names))
    w = 0.38
    for ax, (key, label, is_time) in zip(axes, _PAPER_VS_OURS_PANELS):
        scale = 1e6 if is_time else 1.0
        ours_v = np.array([ours[n].get(key, np.nan) * scale for n in names], dtype=float)
        paper_v = np.array([paper.get(n, {}).get(key, np.nan) * scale for n in names], dtype=float)
        ax.bar(x - w / 2, ours_v, w, label="Python (ours)",
               color=[CIPHER_COLORS.get(n, COLORS["blue"]) for n in names])
        ax.bar(x + w / 2, paper_v, w, label="Bài báo (MATLAB)", color=PAPER_COLOR)
        ax.set_xticks(x, [n.upper() for n in names], fontsize=8)
        ax.set_title(label, fontsize=9, fontweight="bold", color=COLORS["navy"])
        if is_time:
            ax.set_yscale("log")
        else:
            finite = np.concatenate([ours_v[np.isfinite(ours_v)], paper_v[np.isfinite(paper_v)]])
            if finite.size:
                lo, hi = finite.min(), finite.max()
                pad = max((hi - lo) * 0.6, abs(hi) * 0.002, 1e-6)
                ax.set_ylim(lo - pad, hi + pad)
        _style_axes(ax)
    axes[0].legend(fontsize=7, loc="lower left")
    fig.tight_layout()


def draw_class_distributions(fig: Figure, details: pd.DataFrame) -> None:
    """Box plots of PSNR / SSIM / Entropy stego per Linnaeus 5 class."""
    axes = fig.subplots(1, 3)
    if details.empty:
        for ax in axes:
            ax.axis("off")
        axes[1].text(0.5, 0.5, "Không có dữ liệu cho bộ lọc này", ha="center", va="center")
        return
    classes = sorted(details["class_name"].unique())
    for ax, (col, label) in zip(axes, (("psnr", "PSNR (dB)"), ("ssim", "SSIM"),
                                       ("entropy_stego", "Entropy Stego (bits)"))):
        data = [details.loc[details["class_name"] == c, col].to_numpy() for c in classes]
        box = ax.boxplot(data, patch_artist=True, showfliers=False, widths=0.6)
        for patch in box["boxes"]:
            patch.set_facecolor("#DBE7FB")
            patch.set_edgecolor(COLORS["navy"])
        for median in box["medians"]:
            median.set_color(COLORS["bad"])
        ax.set_xticks(np.arange(1, len(classes) + 1), classes, fontsize=8, rotation=20)
        ax.set_title(label, fontsize=9, fontweight="bold", color=COLORS["navy"])
        _style_axes(ax)
    fig.tight_layout()


def draw_enctime_distribution(fig: Figure, details: pd.DataFrame) -> None:
    """Histogram of EncTime (µs, log bins) per cipher."""
    ax = fig.add_subplot(111)
    if details.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, "Không có dữ liệu cho bộ lọc này", ha="center", va="center")
        return
    us = details["enc_time_s"].to_numpy(dtype=float) * 1e6
    us = us[us > 0]
    bins = np.logspace(np.log10(us.min()), np.log10(us.max()), 60) if us.size else 10
    for name in ("3des", "aes", "chaotic"):
        sub = details.loc[details["cipher"] == name, "enc_time_s"].to_numpy(dtype=float) * 1e6
        sub = sub[sub > 0]
        if sub.size:
            ax.hist(sub, bins=bins, alpha=0.75, color=CIPHER_COLORS[name],
                    label=f"{CIPHER_TITLES[name]} (median {np.median(sub):,.1f} µs)")
    ax.set_xscale("log")
    ax.set_xlabel("EncTime (µs, thang log)", fontsize=9)
    ax.set_ylabel("Số lượt", fontsize=9)
    ax.legend(fontsize=8)
    _style_axes(ax)
    fig.tight_layout()
