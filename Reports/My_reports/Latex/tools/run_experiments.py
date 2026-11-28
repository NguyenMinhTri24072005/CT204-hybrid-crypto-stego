r"""Thực nghiệm bổ sung cho báo cáo CT204 (chạy lại được, không sửa code lõi trong SOURCES).

Chạy từ thư mục SOURCES (để dùng đúng venv và package ``src``):

    .\.venv\Scripts\python.exe ..\Reports\My_reports\Latex\tools\run_experiments.py

Kết quả:
    figures/generated/*.png          hình minh họa cho Chương 3
    tools/out/experiments.json       toàn bộ số liệu dùng trong các bảng của báo cáo
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

LATEX_DIR = Path(__file__).resolve().parents[1]
SOURCES = LATEX_DIR.parents[2] / "SOURCES"
sys.path.insert(0, str(SOURCES))

import cv2  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from Crypto.Cipher import AES, DES3  # noqa: E402
from scipy.stats import chi2 as chi2_dist  # noqa: E402
from skimage import data as skdata  # noqa: E402

from src.config import load_config  # noqa: E402
from src.crypto import AESCipher, ChaoticCipher, DES3Cipher, create_cipher  # noqa: E402
from src.crypto.base import ciphertext_to_image_view  # noqa: E402
from src.metrics.security import (  # noqa: E402
    adjacent_pixel_correlation,
    npcr,
    shannon_entropy,
    uaci,
)
from src.metrics.visual import psnr  # noqa: E402
from src.pipeline import read_gray, read_rgb  # noqa: E402
from src.stego.lsb import embed  # noqa: E402
from src.ui.controller import (  # noqa: E402
    build_wrong_key_cipher,
    run_decrypt_workflow,
    run_encrypt_workflow,
    simulate_tamper,
)

OUT_FIG = LATEX_DIR / "figures" / "generated"
OUT_JSON = LATEX_DIR / "tools" / "out"
OUT_FIG.mkdir(parents=True, exist_ok=True)
OUT_JSON.mkdir(parents=True, exist_ok=True)

CIPHERS = ("3des", "aes", "chaotic")
LABELS = {"3des": "3DES", "aes": "AES-128", "chaotic": "Chaotic + PRNG"}

plt.rcParams.update({
    "font.family": "Times New Roman",
    "mathtext.fontset": "stix",
    "font.size": 10,
    "axes.titlesize": 10,
    "savefig.dpi": 220,
    "savefig.bbox": "tight",
})


def view(ct: bytes, shape: tuple[int, int]) -> np.ndarray:
    return ciphertext_to_image_view(ct, shape)


def raw_block_decrypt(cipher, ct: bytes) -> bytes:
    """CBC decrypt without unpad (to visualise what a wrong key produces)."""
    if isinstance(cipher, AESCipher):
        return AES.new(cipher.key, AES.MODE_CBC, iv=cipher.iv).decrypt(ct)
    if isinstance(cipher, DES3Cipher):
        return DES3.new(cipher.key, DES3.MODE_CBC, iv=cipher.iv).decrypt(ct)
    return cipher.decrypt(ct)


def flip_key_bit(key: bytes, byte_i: int, mask: int) -> bytes:
    b = bytearray(key)
    b[byte_i] ^= mask
    return bytes(b)


def chi_square_uniform(img: np.ndarray) -> float:
    counts = np.bincount(img.reshape(-1), minlength=256).astype(np.float64)
    expected = img.size / 256.0
    return float(np.sum((counts - expected) ** 2 / expected))


def pov_chi_square_pvalue(img: np.ndarray) -> float:
    """Westfeld–Pfitzmann pairs-of-values test: p ≈ 1 ⇒ LSB plane looks fully embedded."""
    h = np.bincount(img.reshape(-1), minlength=256).astype(np.float64)
    even, odd = h[0::2], h[1::2]
    expected = (even + odd) / 2.0
    keep = expected > 0
    stat = float(np.sum((even[keep] - expected[keep]) ** 2 / expected[keep]))
    dof = int(keep.sum()) - 1
    return float(chi2_dist.sf(stat, dof)) if dof > 0 else 0.0


def main() -> None:
    cfg = load_config()
    sample = Path(cfg["paths"]["sample_dir"])
    cover = read_rgb(sample / "cover.jpg", size=tuple(cfg["stego"]["cover_size"]))
    secret_full = read_gray(cfg["secret"]["path"])
    secret = read_gray(cfg["secret"]["path"], size=(156, 156))
    shape = secret.shape
    p_bytes = secret.tobytes()
    out: dict = {"secret_shape": list(shape), "secret_full_shape": list(secret_full.shape)}

    ciphers = {c: create_cipher(c, cfg) for c in CIPHERS}
    for c in ciphers.values():
        c.warmup()
    cts = {c: ciphers[c].encrypt(p_bytes) for c in CIPHERS}
    views = {c: view(cts[c], shape) for c in CIPHERS}

    # ---------------------------------------------------------------- E1: key sensitivity
    base_aes, base_3des = ciphers["aes"], ciphers["3des"]
    variants = {
        "3des": [("Đảo 1 bit của khóa K1 (bit 1, byte 0)",
                  DES3Cipher(flip_key_bit(base_3des.key, 0, 0x02), base_3des.iv))],
        "aes": [("Đảo 1 bit của khóa (bit 0, byte 0)",
                 AESCipher(flip_key_bit(base_aes.key, 0, 0x01), base_aes.iv))],
        "chaotic": [
            ("x0 + 1e-10", ChaoticCipher(0.785398 + 1e-10, 3.999, 42)),
            ("r + 1e-10", ChaoticCipher(0.785398, 3.999 + 1e-10, 42)),
            ("ecc_seed 42 → 43", ChaoticCipher(0.785398, 3.999, 43)),
        ],
    }
    key_sens = []
    for name, items in variants.items():
        for desc, alt in items:
            alt.warmup()
            ct2 = alt.encrypt(p_bytes)
            v2 = view(ct2, shape)
            dec = raw_block_decrypt(alt, cts[name])
            dec_img = view(dec, shape)
            key_sens.append({
                "cipher": name, "change": desc,
                "npcr_ct": npcr(views[name], v2), "uaci_ct": uaci(views[name], v2),
                "psnr_wrong_dec": psnr(secret, dec_img),
                "npcr_wrong_dec": npcr(secret, dec_img),
            })
    out["key_sensitivity"] = key_sens

    # ------------------------------------------------------- E2: plaintext sensitivity
    diff = []
    for pos_name, (i, j) in {"Điểm ảnh đầu (0,0)": (0, 0),
                             "Điểm ảnh giữa (78,78)": (78, 78),
                             "Điểm ảnh cuối (155,155)": (155, 155)}.items():
        s2 = secret.copy()
        s2[i, j] = np.uint8((int(s2[i, j]) + 1) % 256)
        for name in CIPHERS:
            v2 = view(ciphers[name].encrypt(s2.tobytes()), shape)
            diff.append({"cipher": name, "position": pos_name,
                         "npcr": npcr(views[name], v2), "uaci": uaci(views[name], v2)})
    out["plaintext_sensitivity"] = diff

    # --------------------------------------------- E3: statistics of encrypted images
    stats = []
    for label, img in [("secret", secret)] + [(c, views[c]) for c in CIPHERS]:
        stats.append({
            "image": label,
            "corr_h": adjacent_pixel_correlation(img, "horizontal"),
            "corr_v": adjacent_pixel_correlation(img, "vertical"),
            "corr_d": adjacent_pixel_correlation(img, "diagonal"),
            "entropy": shannon_entropy(img),
            "chi2": chi_square_uniform(img),
        })
    out["cipher_statistics"] = stats
    out["chi2_critical_0.05_255"] = float(chi2_dist.ppf(0.95, 255))

    # adjacent-pixel scatter (horizontal) — secret vs AES vs Chaotic
    rng = np.random.default_rng(7)
    fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.1), sharey=True)
    for ax, (label, img) in zip(axes, [("Ảnh bí mật", secret)] +
                                [(LABELS[c], views[c]) for c in CIPHERS]):
        ys = rng.integers(0, img.shape[0], 3000)
        xs = rng.integers(0, img.shape[1] - 1, 3000)
        ax.scatter(img[ys, xs], img[ys, xs + 1], s=0.6, c="#1f4e8c", alpha=0.6, linewidths=0)
        ax.set_title(label)
        ax.set_xlim(0, 255); ax.set_ylim(0, 255)
        ax.set_xticks([0, 128, 255]); ax.set_yticks([0, 128, 255])
        ax.set_aspect("equal")
        ax.set_xlabel("$p(x, y)$")
    axes[0].set_ylabel("$p(x+1, y)$")
    fig.subplots_adjust(wspace=0.12)
    fig.savefig(OUT_FIG / "adjacent_scatter.png")
    plt.close(fig)

    # ----------------------------------------------------- E4: tamper lab (controller)
    tamper = []
    tamper_imgs: dict = {}
    modes = ["baseline", "wrong_key", "jpeg_q95", "flip_header_bit", "flip_payload_bits",
             "gaussian_noise"]
    for name in CIPHERS:
        res = run_encrypt_workflow(cover, secret, cfg, cipher_name=name, normalize=False)
        for mode in modes:
            stego = res.stego_rgb
            cipher = None
            if mode == "wrong_key":
                cipher, _ = build_wrong_key_cipher(name, cfg)
            elif mode != "baseline":
                stego, _ = simulate_tamper(res.stego_rgb, mode)
            dec = run_decrypt_workflow(stego, cfg, cipher_name=name, cipher=cipher,
                                       reference_secret_gray=secret)
            tamper.append({
                "cipher": name, "mode": mode, "stage": dec.stage, "success": dec.success,
                "is_exact": bool(dec.is_exact) if dec.is_exact is not None else False,
                "psnr": dec.recovery_psnr, "ber": dec.bit_error_rate,
                "header_valid": dec.header.is_valid,
                "message": dec.message,
            })
            tamper_imgs[(name, mode)] = dec.display_image
    out["tamper"] = tamper

    # figure: AES vs Chaotic under payload flips / Gaussian noise / wrong key
    cols = [("baseline", "Không tấn công"), ("flip_payload_bits", "Đảo 1% bit payload"),
            ("wrong_key", "Sai khóa (seed + 1)"), ("gaussian_noise", "Nhiễu Gauss σ = 2")]
    fig, axes = plt.subplots(3, 4, figsize=(7.0, 5.6))
    for r, name in enumerate(CIPHERS):
        for c, (mode, title) in enumerate(cols):
            ax = axes[r, c]
            img = tamper_imgs.get((name, mode))
            row = next(t for t in tamper if t["cipher"] == name and t["mode"] == mode)
            if img is None:
                ax.imshow(np.full(shape, 235, np.uint8), cmap="gray", vmin=0, vmax=255)
                ax.text(0.5, 0.5, "Dừng ở bước\nkiểm tra Header\n(CRC/Magic sai)",
                        ha="center", va="center", transform=ax.transAxes, fontsize=8.5,
                        color="#b91c1c")
            else:
                ax.imshow(img, cmap="gray", vmin=0, vmax=255)
                p = row["psnr"]
                tag = "∞" if p is not None and np.isinf(p) else (f"{p:.2f} dB" if p else "—")
                ax.set_xlabel(f"PSNR = {tag}", fontsize=8.5)
            ax.set_xticks([]); ax.set_yticks([])
            if r == 0:
                ax.set_title(title, fontsize=9)
            if c == 0:
                ax.set_ylabel(LABELS[name], fontsize=9.5)
    fig.tight_layout()
    fig.savefig(OUT_FIG / "tamper_grid.png")
    plt.close(fig)

    # ------------------------------------- E5: known-plaintext / two-time-pad attack
    other = cv2.resize(skdata.camera(), (156, 156), interpolation=cv2.INTER_AREA)
    kpa = {}
    fig, axes = plt.subplots(2, 4, figsize=(7.0, 3.75))
    for r, name in enumerate(("chaotic", "aes")):
        ciph = ciphers[name]
        ca, cb = cts[name], ciph.encrypt(other.tobytes())
        n = 156 * 156
        keystream = np.frombuffer(p_bytes, np.uint8) ^ np.frombuffer(ca[:n], np.uint8)
        guess_b = (np.frombuffer(cb[:n], np.uint8) ^ keystream).reshape(156, 156)
        xor_ct = (np.frombuffer(ca[:n], np.uint8) ^ np.frombuffer(cb[:n], np.uint8)).reshape(156, 156)
        kpa[name] = {
            "recovered_exact": bool(np.array_equal(guess_b, other)),
            "psnr_guess": psnr(other, guess_b),
            "npcr_guess": npcr(other, guess_b),
            "corr_xor_vs_plain_xor": float(np.corrcoef(
                xor_ct.ravel().astype(float),
                (secret ^ other).ravel().astype(float))[0, 1]),
        }
        panels = [(other, "Ảnh B (bí mật)"), (view(cb, shape), "Bản mã $C_B$"),
                  (xor_ct, "$C_A \\oplus C_B$"), (guess_b, "$C_B \\oplus (A \\oplus C_A)$")]
        for c, (img, title) in enumerate(panels):
            ax = axes[r, c]
            ax.imshow(img, cmap="gray", vmin=0, vmax=255)
            ax.set_xticks([]); ax.set_yticks([])
            if r == 0:
                ax.set_title(title, fontsize=9.5)
            if c == 0:
                ax.set_ylabel(LABELS[name], fontsize=9.5)
    fig.tight_layout()
    fig.savefig(OUT_FIG / "kpa_attack.png")
    plt.close(fig)
    out["known_plaintext"] = kpa

    # ------------------------------ E6: embedding distortion (1-LSB vs 3-LSB + scale-up)
    emb_rows = []
    fig, axes = plt.subplots(2, 4, figsize=(7.2, 3.9))
    for r, (sec, title, gain) in enumerate([(secret, "1-LSB (156×156)", 85),
                                             (secret_full, "3-LSB + phóng đại (246×300)", 32)]):
        ct = ciphers["aes"].encrypt(sec.tobytes())
        e = embed(cover, ct, sec.shape, max_lsb=3)
        d = np.abs(e.cover_used_rgb.astype(np.int16) - e.stego_rgb.astype(np.int16))
        emb_rows.append({"case": title, "num_lsb": e.num_lsb,
                         "cover_used": list(e.cover_used_rgb.shape[:2]),
                         "scaled": e.was_scaled_up, "max_abs_diff": int(d.max()),
                         "changed_ratio": float(np.count_nonzero(d) / d.size)})
        lsb_plane = (e.stego_rgb[..., 0] & 1) * 255
        panels = [(e.cover_used_rgb, "Ảnh phủ"), (e.stego_rgb, "Ảnh stego"),
                  (np.clip(d * gain, 0, 255).astype(np.uint8), f"|phủ − stego| × {gain}"),
                  (lsb_plane, "Mặt phẳng bit 0 (kênh R)")]
        for c, (img, ttl) in enumerate(panels):
            ax = axes[r, c]
            ax.imshow(img, cmap=None if img.ndim == 3 else "gray", vmin=0, vmax=255)
            ax.set_xticks([]); ax.set_yticks([])
            if r == 0:
                ax.set_title(ttl, fontsize=9.5)
            if c == 0:
                ax.set_ylabel(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_FIG / "embedding_distortion.png")
    plt.close(fig)
    out["embedding"] = emb_rows

    # cover LSB plane alone (for comparison with the stego LSB plane)
    fig, axes = plt.subplots(1, 2, figsize=(4.2, 2.2))
    axes[0].imshow((cover[..., 0] & 1) * 255, cmap="gray"); axes[0].set_title("Ảnh phủ gốc")
    ct = ciphers["aes"].encrypt(p_bytes)
    st = embed(cover, ct, shape, max_lsb=3).stego_rgb
    axes[1].imshow((st[..., 0] & 1) * 255, cmap="gray"); axes[1].set_title("Ảnh stego (1-LSB)")
    for ax in axes:
        ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(OUT_FIG / "lsb_plane.png")
    plt.close(fig)

    # --------------------------- E7: chi-square steganalysis over all Linnaeus 5 covers
    data_dir = Path(cfg["paths"]["data_dir"])
    files = sorted(data_dir.glob("*/*/*.jpg"))
    t0 = time.perf_counter()
    p_cover, p_stego = [], []
    aes = ciphers["aes"]
    for f in files:
        cv_img = read_rgb(f, size=(256, 256))
        st = embed(cv_img, aes.encrypt(p_bytes), shape, max_lsb=3).stego_rgb
        p_cover.append(pov_chi_square_pvalue(cv_img))
        p_stego.append(pov_chi_square_pvalue(st))
    p_cover, p_stego = np.array(p_cover), np.array(p_stego)
    out["steganalysis"] = {
        "n_images": int(len(files)),
        "seconds": time.perf_counter() - t0,
        "threshold": 0.95,
        "cover_flagged_rate": float(np.mean(p_cover > 0.95)),
        "stego_flagged_rate": float(np.mean(p_stego > 0.95)),
        "cover_p_median": float(np.median(p_cover)),
        "stego_p_median": float(np.median(p_stego)),
    }
    fig, ax = plt.subplots(figsize=(5.6, 2.3))
    bins = np.linspace(0, 1, 41)
    ax.hist(p_cover, bins=bins, color="#2563eb", alpha=0.75, label="Ảnh phủ gốc")
    ax.hist(p_stego, bins=bins, color="#dc2626", alpha=0.75, label="Ảnh stego (1-LSB, 99% sức chứa)")
    ax.axvline(0.95, color="black", ls="--", lw=1)
    ax.set_yscale("log")
    ax.set_xlabel("Giá trị $p$ của kiểm định $\\chi^2$ cặp giá trị (PoV)")
    ax.set_ylabel("Số ảnh (thang log)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper center")
    fig.savefig(OUT_FIG / "chi2_steganalysis.png")
    plt.close(fig)

    (OUT_JSON / "experiments.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
