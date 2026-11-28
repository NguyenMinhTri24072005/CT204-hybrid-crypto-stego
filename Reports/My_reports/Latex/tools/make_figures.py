r"""Sinh biểu đồ cho báo cáo từ các file CSV benchmark và sao chép ảnh kết quả của dự án.

Chạy từ thư mục SOURCES:

    .\.venv\Scripts\python.exe ..\Reports\My_reports\Latex\tools\make_figures.py

Đầu vào : SOURCES/results/benchmark_summary_table2.csv, benchmark_results.csv, single/*
Đầu ra  : figures/generated/*.png, figures/results/*.png, tools/out/summary.json
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

LATEX_DIR = Path(__file__).resolve().parents[1]
PROJECT = LATEX_DIR.parents[2]
SOURCES = PROJECT / "SOURCES"
sys.path.insert(0, str(SOURCES))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.pipeline import read_rgb  # noqa: E402

RESULTS = SOURCES / "results"
OUT_GEN = LATEX_DIR / "figures" / "generated"
OUT_RES = LATEX_DIR / "figures" / "results"
OUT_PAPER = LATEX_DIR / "figures" / "paper"
OUT_JSON = LATEX_DIR / "tools" / "out"
for d in (OUT_GEN, OUT_RES, OUT_PAPER, OUT_JSON):
    d.mkdir(parents=True, exist_ok=True)

CIPHERS = ["3des", "aes", "chaotic"]
LABELS = {"3des": "3DES", "aes": "AES-128", "chaotic": "Chaotic"}
C_PAPER = "#9ca3af"
C_OURS = "#1f4e8c"
C_ALT = "#d97706"

# Bảng 2 của bài báo gốc (MATLAB R2024a)
PAPER = {
    "3des": dict(mse=0.499975, psnr=51.15389, ssim=0.998495, enc=0.003552, npcr=99.59214,
                 uaci=30.80843, corr=0.00032, ent=7.047627),
    "aes": dict(mse=0.500006, psnr=51.15373, ssim=0.998494, enc=0.000601, npcr=99.61924,
                uaci=30.81756, corr=-0.00407, ent=7.047762),
    "chaotic": dict(mse=0.499321, psnr=51.14436, ssim=0.998099, enc=3.62e-05, npcr=99.63957,
                    uaci=30.96067, corr=-0.00984, ent=6.952836),
}

plt.rcParams.update({
    "font.family": "Times New Roman",
    "mathtext.fontset": "stix",
    "font.size": 10,
    "axes.titlesize": 10.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.dpi": 220,
    "savefig.bbox": "tight",
})


def bar_labels(ax, bars, fmt, rotation=0, size=7.5):
    for b in bars:
        h = b.get_height()
        ax.annotate(fmt(h), (b.get_x() + b.get_width() / 2, h), xytext=(0, 2),
                    textcoords="offset points", ha="center", va="bottom", fontsize=size,
                    rotation=rotation)


def main() -> None:
    summary = pd.read_csv(RESULTS / "benchmark_summary_table2.csv").set_index("cipher")
    details = pd.read_csv(RESULTS / "benchmark_results.csv")
    single = pd.read_csv(RESULTS / "single" / "single_metrics.csv").set_index("cipher")

    # ----------------------------------------------------------- copy project images
    for f in (RESULTS / "single").glob("*.png"):
        shutil.copy2(f, OUT_RES / f.name)
    assets = PROJECT / "Docs" / "145987_assets"
    for name in ("fig3_linnaeus5_cover_samples.jpeg", "fig5_aes_encrypted_hist.jpeg",
                 "fig4c_cover_histogram.jpeg", "fig5_aes_stego_hist.jpeg"):
        if (assets / name).is_file():
            shutil.copy2(assets / name, OUT_PAPER / name)

    x = np.arange(len(CIPHERS))
    w = 0.36

    # ------------------------------------------- 1) visual quality: paper vs ours
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7))
    specs = [("mse", "avg_mse", "std_mse", "MSE (↓)", (0.48, 0.508), lambda v: f"{v:.4f}"),
             ("psnr", "avg_psnr", "std_psnr", "PSNR (dB, ↑)", (51.0, 51.27), lambda v: f"{v:.3f}"),
             ("ssim", "avg_ssim", "std_ssim", "SSIM (↑)", (0.995, 0.9993), lambda v: f"{v:.4f}")]
    for ax, (pk, col, std, title, ylim, fmt) in zip(axes, specs):
        b1 = ax.bar(x - w / 2, [PAPER[c][pk] for c in CIPHERS], w, color=C_PAPER, label="Bài báo (MATLAB)")
        b2 = ax.bar(x + w / 2, summary.loc[CIPHERS, col], w, color=C_OURS,
                    label="Tái hiện (Python, TB 8000 ảnh)")
        ax.set_ylim(*ylim)
        ax.set_xticks(x, [LABELS[c] for c in CIPHERS])
        ax.set_title(title)
        bar_labels(ax, b1, fmt, rotation=90, size=7)
        bar_labels(ax, b2, fmt, rotation=90, size=7)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, fontsize=8.5)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(OUT_GEN / "visual_paper_vs_ours.png")
    plt.close(fig)

    # ------------------------------------------------------- 2) EncTime (log scale)
    fig, ax = plt.subplots(figsize=(6.2, 2.7))
    ww = 0.26
    t_paper = [PAPER[c]["enc"] * 1e6 for c in CIPHERS]
    t_156 = [summary.loc[c, "avg_enc_time_s"] * 1e6 for c in CIPHERS]
    t_246 = [single.loc[c, "enc_time_s"] * 1e6 for c in CIPHERS]
    bars = [ax.bar(x - ww, t_paper, ww, color=C_PAPER, label="Bài báo (MATLAB R2024a)"),
            ax.bar(x, t_156, ww, color=C_OURS, label="Python — 156×156, TB 8000 ảnh (Chaotic: mặt nạ cache)"),
            ax.bar(x + ww, t_246, ww, color=C_ALT, label="Python — 246×300, 1 lần chạy (Chaotic: sinh lại mặt nạ)")]
    for bs in bars:
        bar_labels(ax, bs, lambda v: f"{v:.0f}" if v >= 100 else f"{v:.1f}")
    ax.set_yscale("log")
    ax.set_ylim(10, 4e4)
    ax.set_ylabel("Thời gian mã hóa (µs, thang log)")
    ax.set_xticks(x, [LABELS[c] for c in CIPHERS])
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT_GEN / "enctime_compare.png")
    plt.close(fig)

    # ------------------------------------------- 3) EncTime distribution (8,000 runs)
    fig, ax = plt.subplots(figsize=(6.2, 2.4))
    data = [details.loc[details.cipher == c, "enc_time_s"].to_numpy() * 1e6 for c in CIPHERS]
    bp = ax.boxplot(data, vert=False, widths=0.55, showfliers=True, patch_artist=True,
                    flierprops=dict(marker=".", markersize=2, alpha=0.3))
    for patch in bp["boxes"]:
        patch.set_facecolor("#dbe5f3")
    ax.set_xscale("log")
    ax.set_yticks([1, 2, 3], [LABELS[c] for c in CIPHERS])
    ax.set_xlabel("EncTime mỗi ảnh (µs, thang log) — 8000 lượt/thuật toán")
    fig.tight_layout()
    fig.savefig(OUT_GEN / "enctime_distribution.png")
    plt.close(fig)

    # --------------------------------------------- 4) dual metrics enc vs stego
    fig, axes = plt.subplots(1, 4, figsize=(7.4, 2.4))
    pairs = [("avg_entropy_enc", "avg_entropy_stego", "Entropy (bit)", (0, 8.8), "{:.3f}"),
             ("avg_npcr_enc", "avg_npcr_stego", "NPCR (%)", (0, 112), "{:.2f}"),
             ("avg_uaci_enc", "avg_uaci_stego", "UACI (%)", (0, 36), "{:.2f}"),
             ("avg_corr_enc", "avg_corr_stego", "Hệ số tương quan", (-0.1, 1.15), "{:.3f}")]
    for ax, (ce, cs, title, ylim, fmt) in zip(axes, pairs):
        b1 = ax.bar(x - w / 2, summary.loc[CIPHERS, ce], w, color=C_OURS, label="Bản mã (*_enc)")
        b2 = ax.bar(x + w / 2, summary.loc[CIPHERS, cs], w, color=C_ALT, label="Ảnh stego (*_stego)")
        ax.set_ylim(*ylim)
        ax.set_title(title)
        ax.set_xticks(x, ["3DES", "AES", "Chaos"], fontsize=8.5)
        for bs in (b1, b2):
            bar_labels(ax, bs, lambda v, f=fmt: f.format(v), size=6.5)
        ax.axhline(0, color="black", lw=0.6)
    axes[0].axhline(7.05, color="#374151", ls=":", lw=1.2, label="Entropy công bố trong bài báo (≈ 7.05)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(OUT_GEN / "dual_metrics.png")
    plt.close(fig)

    # --------------------------------------------- 5) per-class analysis (AES rows)
    aes = details[details.cipher == "aes"]
    classes = ["berry", "bird", "dog", "flower", "other"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6))
    axes[0].boxplot([aes.loc[aes.class_name == k, "ssim"] for k in classes], widths=0.55,
                    showfliers=False, patch_artist=True,
                    boxprops=dict(facecolor="#dbe5f3"))
    axes[0].set_xticks(range(1, 6), classes)
    axes[0].set_title("SSIM ảnh stego theo lớp (AES, 1600 ảnh/lớp)")
    ent = aes.groupby("class_name")["entropy_stego"].mean().loc[classes]
    ssim_mean = aes.groupby("class_name")["ssim"].mean().loc[classes]
    bars = axes[1].bar(classes, ent, color=C_OURS)
    bar_labels(axes[1], bars, lambda v: f"{v:.2f}")
    axes[1].set_ylim(7.0, 7.7)
    axes[1].set_title("Entropy trung bình của ảnh stego theo lớp")
    fig.tight_layout()
    fig.savefig(OUT_GEN / "class_analysis.png")
    plt.close(fig)

    # ------------------------------------------------- 6) PSNR / SSIM distributions
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.4))
    colors = {"3des": "#6b7280", "aes": C_OURS, "chaotic": C_ALT}
    for c in CIPHERS:
        sub = details[details.cipher == c]
        axes[0].hist(sub["psnr"], bins=60, histtype="step", lw=1.1, color=colors[c], label=LABELS[c])
        axes[1].hist(sub["ssim"], bins=60, histtype="step", lw=1.1, color=colors[c], label=LABELS[c])
    axes[0].axvline(10 * np.log10(255**2 / 0.5), color="black", ls=":", lw=1)
    axes[0].set_xlabel("PSNR (dB)")
    axes[1].set_xlabel("SSIM")
    axes[0].set_ylabel("Số ảnh")
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_GEN / "psnr_ssim_distribution.png")
    plt.close(fig)

    # ------------------------------------------------ 7) Linnaeus 5 sample grid
    data_dir = SOURCES / "data" / "linnaeus5" / "train"
    fig, axes = plt.subplots(5, 7, figsize=(7.0, 5.2))
    for r, k in enumerate(classes):
        files = sorted((data_dir / k).glob("*.jpg"))[:7]
        for c, f in enumerate(files):
            ax = axes[r, c]
            ax.imshow(read_rgb(f))
            ax.set_xticks([]); ax.set_yticks([])
            for s in ax.spines.values():
                s.set_visible(False)
            if c == 0:
                ax.set_ylabel(k, fontsize=10)
    fig.subplots_adjust(wspace=0.04, hspace=0.04)
    fig.savefig(OUT_GEN / "linnaeus5_samples.png")
    plt.close(fig)

    # ---------------------------------------------------------- numbers for the text
    info = {
        "n_rows": int(len(details)),
        "exact_recovery_all": bool(details["exact_recovery"].all()),
        "num_lsb_values": sorted(details["num_lsb"].unique().tolist()),
        "scaled_any": bool(details["was_scaled_up"].any()),
        "class_ssim_aes": ssim_mean.round(5).to_dict(),
        "class_entropy_aes": ent.round(3).to_dict(),
        "split_psnr": details.groupby(["cipher", "split"])["psnr"].mean().round(4).unstack().to_dict(),
        "split_ssim": details.groupby(["cipher", "split"])["ssim"].mean().round(5).unstack().to_dict(),
        "enctime_median_us": {c: float(np.median(d)) for c, d in zip(CIPHERS, data)},
        "enctime_p95_us": {c: float(np.percentile(d, 95)) for c, d in zip(CIPHERS, data)},
        "psnr_min_max": {c: [float(details.loc[details.cipher == c, "psnr"].min()),
                             float(details.loc[details.cipher == c, "psnr"].max())] for c in CIPHERS},
        "ssim_min_max": {c: [float(details.loc[details.cipher == c, "ssim"].min()),
                             float(details.loc[details.cipher == c, "ssim"].max())] for c in CIPHERS},
    }
    (OUT_JSON / "summary.json").write_text(json.dumps(info, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
    print(json.dumps(info, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
