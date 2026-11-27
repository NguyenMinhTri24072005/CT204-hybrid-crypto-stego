"""Phase 4 tests: visual metrics, dual security metrics, and CLI scripts (BM-08, BM-09, BM-10)."""

from __future__ import annotations

import math
import time

import cv2
import numpy as np
import pandas as pd
import pytest

from scripts import run_benchmark, run_single
from src.config import load_config
from src.crypto import BaseCipher, ChaoticCipher, create_cipher
from src.metrics import (
    adjacent_pixel_correlation,
    compute_all_metrics,
    compute_dual_security_metrics,
    compute_visual_metrics,
    cross_correlation,
    measure_enc_time,
    mse,
    npcr,
    psnr,
    shannon_entropy,
    ssim,
    uaci,
)
from src.pipeline import read_gray, read_rgb, run_from_config


@pytest.fixture(scope="module")
def cfg():
    return load_config()


# --------------------------------------------------------------------------- visual.py
class TestVisualMetrics:
    def test_identical_images(self):
        img = np.random.default_rng(10).integers(0, 256, (64, 64, 3), dtype=np.uint8)
        assert mse(img, img) == 0.0
        assert math.isinf(psnr(img, img))
        assert ssim(img, img) == pytest.approx(1.0)

    def test_mse_rgb_divides_by_all_three_channels_bm09(self):
        # BM-09: half of all H*W*3 channel values differ by 1 -> MSE == 0.5, PSNR == 51.1411 dB.
        a = np.zeros((32, 32, 3), dtype=np.uint8)
        b = a.copy()
        flat = b.reshape(-1)
        flat[: flat.size // 2] = 1
        assert mse(a, b) == pytest.approx(0.5, abs=1e-12)
        assert psnr(a, b) == pytest.approx(10.0 * math.log10(255.0**2 / 0.5), rel=1e-12)

    def test_no_uint8_underflow_in_mse(self):
        zeros = np.zeros((16, 16, 3), dtype=np.uint8)
        ones = np.full((16, 16, 3), 255, dtype=np.uint8)
        assert mse(zeros, ones) == pytest.approx(255.0**2)
        assert mse(ones, zeros) == pytest.approx(255.0**2)
        assert psnr(zeros, ones) == pytest.approx(0.0, abs=1e-12)

    def test_ssim_2d_and_small_window(self):
        a = np.arange(25, dtype=np.uint8).reshape(5, 5)
        b = a.copy()
        assert ssim(a, b) == pytest.approx(1.0)
        with pytest.raises(ValueError):
            ssim(np.zeros((2, 2), dtype=np.uint8), np.zeros((2, 2), dtype=np.uint8))

    def test_ssim_uses_gaussian_weights_matching_matlab_bm09(self):
        from skimage.metrics import structural_similarity

        rng = np.random.default_rng(42)
        a = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
        b = a.copy()
        b[8:16, 8:16] = 255 - b[8:16, 8:16]
        expected_gauss = float(
            structural_similarity(
                a,
                b,
                data_range=255,
                channel_axis=-1,
                gaussian_weights=True,
                sigma=1.5,
                use_sample_covariance=False,
            )
        )
        uniform_box = float(structural_similarity(a, b, data_range=255, channel_axis=-1))
        assert ssim(a, b) == pytest.approx(expected_gauss, abs=1e-12)
        assert abs(ssim(a, b) - uniform_box) > 1e-3

    def test_compute_visual_metrics_keys(self):
        a = np.full((32, 32, 3), 100, dtype=np.uint8)
        b = np.full((32, 32, 3), 101, dtype=np.uint8)
        res = compute_visual_metrics(a, b)
        assert set(res) == {"mse", "psnr", "ssim"}
        assert res["mse"] == pytest.approx(1.0)
        assert res["psnr"] == pytest.approx(10.0 * math.log10(255.0**2))

    @pytest.mark.parametrize(
        "a,b",
        [
            (np.zeros((8, 8, 3), np.uint8), np.zeros((8, 9, 3), np.uint8)),
            (np.zeros((8, 8, 3), np.float32), np.zeros((8, 8, 3), np.float32)),
            (np.zeros((8,), np.uint8), np.zeros((8,), np.uint8)),
            (np.zeros((0, 8), np.uint8), np.zeros((0, 8), np.uint8)),
        ],
    )
    def test_rejects_invalid_pairs(self, a, b):
        with pytest.raises(ValueError):
            mse(a, b)


# ------------------------------------------------------------------------- security.py
class TestSecurityMetrics:
    def test_npcr_exact_values(self):
        a = np.zeros((10, 20), dtype=np.uint8)
        b = np.zeros((10, 20), dtype=np.uint8)
        assert npcr(a, b) == 0.0
        b[:5, :] = 1
        assert npcr(a, b) == pytest.approx(50.0)
        b[:, :] = 7
        assert npcr(a, b) == pytest.approx(100.0)

    def test_uaci_symmetric_and_no_uint8_underflow(self):
        a = np.full((16, 16), 10, dtype=np.uint8)
        b = np.full((16, 16), 35, dtype=np.uint8)
        expected = (25.0 / 255.0) * 100.0
        assert uaci(a, b) == pytest.approx(expected)
        assert uaci(b, a) == pytest.approx(expected)
        assert uaci(np.zeros((4, 4), np.uint8), np.full((4, 4), 255, np.uint8)) == pytest.approx(100.0)

    def test_shannon_entropy_known_distributions(self):
        assert shannon_entropy(np.full((32, 32), 42, dtype=np.uint8)) == 0.0
        half = np.array([0, 255] * 512, dtype=np.uint8).reshape(32, 32)
        assert shannon_entropy(half) == pytest.approx(1.0)
        uniform = np.repeat(np.arange(256, dtype=np.uint8), 64).reshape(128, 128)
        assert shannon_entropy(uniform) == pytest.approx(8.0, abs=1e-12)

    def test_cross_correlation_2d_and_3d_matches_numpy_bm09(self):
        rng = np.random.default_rng(99)
        g1 = rng.integers(0, 256, (40, 50), dtype=np.uint8)
        g2 = rng.integers(0, 256, (40, 50), dtype=np.uint8)
        expected_2d = float(np.corrcoef(g1.ravel(), g2.ravel())[0, 1])
        assert cross_correlation(g1, g2) == pytest.approx(expected_2d, abs=1e-12)
        assert cross_correlation(g1, g1) == pytest.approx(1.0)
        assert cross_correlation(g1, (255 - g1).astype(np.uint8)) == pytest.approx(-1.0)

        rgb1 = rng.integers(0, 256, (30, 30, 3), dtype=np.uint8)
        rgb2 = rng.integers(0, 256, (30, 30, 3), dtype=np.uint8)
        expected_3d = float(
            np.mean([np.corrcoef(rgb1[..., c].ravel(), rgb2[..., c].ravel())[0, 1] for c in range(3)])
        )
        assert cross_correlation(rgb1, rgb2) == pytest.approx(expected_3d, abs=1e-12)

    def test_cross_correlation_constant_image_returns_zero_without_warning(self):
        const = np.full((16, 16), 128, dtype=np.uint8)
        rand = np.random.default_rng(7).integers(0, 256, (16, 16), dtype=np.uint8)
        assert cross_correlation(const, rand) == 0.0
        assert cross_correlation(const, const) == 0.0

    @pytest.mark.parametrize("direction", ["horizontal", "vertical", "diagonal"])
    def test_adjacent_pixel_correlation(self, direction):
        grad = np.tile(np.arange(128, dtype=np.uint8), (128, 1))
        noise = np.random.default_rng(123).integers(0, 256, (128, 128), dtype=np.uint8)
        if direction != "vertical":
            assert adjacent_pixel_correlation(grad, direction) > 0.95
        assert abs(adjacent_pixel_correlation(noise, direction)) < 0.05

    def test_adjacent_rejects_bad_direction(self):
        with pytest.raises(ValueError):
            adjacent_pixel_correlation(np.zeros((8, 8), dtype=np.uint8), " sideways ")

    def test_measure_enc_time_and_warmup_hook(self, cfg, monkeypatch):
        calls: list[str] = []
        cipher = ChaoticCipher.from_config(cfg)
        real_warmup = cipher.warmup

        def tracked_warmup():
            calls.append("warmup")
            real_warmup()

        monkeypatch.setattr(cipher, "warmup", tracked_warmup)
        ct1, dt1 = measure_enc_time(cipher, b"hello world" * 100, warmup=True)
        assert calls == ["warmup"] and dt1 > 0.0
        ct2, dt2 = measure_enc_time(cipher, b"hello world" * 100, warmup=False)
        assert calls == ["warmup"] and dt2 > 0.0
        assert ct1 == ct2 == cipher.encrypt(b"hello world" * 100)

    def test_dual_metrics_match_table2_regime_bm08(self, cfg):
        res = run_from_config(cfg, "aes", secret_size=(156, 156))
        m = res.metrics
        assert m["mse"] == pytest.approx(0.50, abs=0.02)
        assert m["psnr"] == pytest.approx(51.15, abs=0.25)
        assert m["ssim"] > 0.995
        assert m["npcr_enc"] == pytest.approx(99.61, abs=0.35)
        assert 29.0 <= m["uaci_enc"] <= 33.0
        assert abs(m["corr_enc"]) < 0.05
        assert m["entropy_enc"] > 7.99
        # Stego vs cover has tiny UACI and high correlation, while stego entropy stays natural (~7.x).
        assert m["uaci_stego"] < 0.5
        assert m["corr_stego"] > 0.999
        assert 6.5 <= m["entropy_stego"] <= 7.9

    def test_compute_all_metrics_without_enc_time(self):
        s = np.zeros((16, 16), np.uint8)
        e = np.full((16, 16), 200, np.uint8)
        c = np.full((16, 16, 3), 100, np.uint8)
        st = np.full((16, 16, 3), 101, np.uint8)
        m = compute_all_metrics(s, e, c, st)
        assert "enc_time_s" not in m and len(m) == 11


# ---------------------------------------------------------------------------- scripts/
class TestScripts:
    def test_run_single_generates_images_figures_and_csv(self, tmp_path):
        out_dir = tmp_path / "single_out"
        returned = run_single.main(
            ["--secret-size", "156", "156", "--out-dir", str(out_dir), "--quiet"]
        )
        assert returned == out_dir
        expected_files = [
            "cover.png",
            "secret.png",
            "fig4_cover_secret_histograms.png",
            "fig5_comparison_grid.png",
            "single_metrics.csv",
        ]
        for c in ("3des", "aes", "chaotic"):
            expected_files.extend([f"{c}_encrypted.png", f"{c}_stego.png", f"{c}_recovered.png"])
        for fname in expected_files:
            fpath = out_dir / fname
            assert fpath.is_file() and fpath.stat().st_size > 0

        # Verify saved stego PNGs are exact 256x256 and recovered PNGs equal secret.png.
        sec = read_gray(out_dir / "secret.png")
        assert sec.shape == (156, 156)
        for c in ("3des", "aes", "chaotic"):
            assert read_rgb(out_dir / f"{c}_stego.png").shape == (256, 256, 3)
            assert np.array_equal(read_gray(out_dir / f"{c}_recovered.png"), sec)

        df = pd.read_csv(out_dir / "single_metrics.csv")
        assert list(df["cipher"]) == ["3des", "aes", "chaotic"]
        assert df["exact_recovery"].all()

    def test_run_single_synthesizes_missing_secret(self, tmp_path):
        missing_secret = tmp_path / "auto_secret.png"
        out_dir = tmp_path / "out"
        run_single.main(
            ["--secret", str(missing_secret), "--out-dir", str(out_dir), "--quiet"]
        )
        assert missing_secret.is_file()
        assert cv2.imread(str(missing_secret), cv2.IMREAD_GRAYSCALE).shape == (246, 300)

    def test_run_benchmark_smoke_limit(self, tmp_path):
        out_dir = tmp_path / "bench_out"
        detailed_csv, summary_csv = run_benchmark.main(
            [
                "--limit",
                "4",
                "--secret-size",
                "156",
                "156",
                "--vary-key-per-image",
                "--cache-chaotic-mask",
                "--out-dir",
                str(out_dir),
                "--quiet",
            ]
        )
        assert detailed_csv.is_file() and summary_csv.is_file()
        df = pd.read_csv(detailed_csv)
        summary = pd.read_csv(summary_csv)
        assert len(df) == 4 * 3
        assert len(summary) == 3
        assert list(summary["cipher"]) == ["3des", "aes", "chaotic"]
        assert (summary["exact_recovery_rate"] == 1.0).all()
        assert summary["avg_psnr"].between(50.5, 52.0).all()
        assert summary_csv.name == "benchmark_summary_table2.csv"  # spec §3.3.3
        assert detailed_csv.name == "benchmark_results.csv"


# ------------------------------------------------------------------ audit edge cases
class _SlowCipher(BaseCipher):
    """Test double: warmup and encrypt have known, distinct costs."""

    def __init__(self, warmup_s: float, encrypt_s: float) -> None:
        self.warmup_s, self.encrypt_s = warmup_s, encrypt_s

    @property
    def name(self) -> str:
        return "slow"

    def warmup(self) -> None:
        time.sleep(self.warmup_s)

    def encrypt(self, plaintext: bytes) -> bytes:
        time.sleep(self.encrypt_s)
        return bytes(b ^ 0x5A for b in plaintext)

    def decrypt(self, ciphertext: bytes) -> bytes:
        return bytes(b ^ 0x5A for b in ciphertext)


class TestAuditEdgeCases:
    def test_enc_time_excludes_warmup(self):
        _, dt = measure_enc_time(_SlowCipher(0.30, 0.02), b"abc", warmup=True)
        assert 0.015 <= dt < 0.25

    def test_pipeline_enc_time_excludes_embedding(self, monkeypatch):
        import src.pipeline as pipeline_mod

        real_embed = pipeline_mod.embed

        def slow_embed(*args, **kwargs):
            time.sleep(0.30)
            return real_embed(*args, **kwargs)

        monkeypatch.setattr(pipeline_mod, "embed", slow_embed)
        secret = np.random.default_rng(0).integers(0, 256, (16, 16), dtype=np.uint8)
        cover = np.random.default_rng(1).integers(0, 256, (32, 32, 3), dtype=np.uint8)
        res = pipeline_mod.run_pipeline(secret, cover, _SlowCipher(0.0, 0.02))
        assert res.is_exact
        assert 0.015 <= res.enc_time_s < 0.25

    def test_cached_chaotic_mask_is_precomputed_before_timing(self, cfg):
        # BM-10: cache_mask=True must time the XOR only, even without manual priming.
        cipher = create_cipher("chaotic", cfg, cache_chaotic_mask=True)
        pt = b"\x00" * 73800
        _, dt = measure_enc_time(cipher, pt, warmup=True)
        assert cipher._cached is not None and cipher._cached[0] == len(pt)
        ct_again = cipher.encrypt(pt)
        assert ct_again == create_cipher("chaotic", cfg).encrypt(pt)
        assert dt > 0.0

    def test_uncached_chaotic_is_not_cached_by_timing(self, cfg):
        cipher = create_cipher("chaotic", cfg)
        measure_enc_time(cipher, b"\x01" * 1000, warmup=True)
        assert cipher._cached is None

    def test_correlation_rgb_with_one_constant_channel(self):
        rng = np.random.default_rng(5)
        a = rng.integers(0, 256, (20, 20, 3), dtype=np.uint8)
        b = rng.integers(0, 256, (20, 20, 3), dtype=np.uint8)
        a[..., 1] = 77  # zero variance in G -> that channel contributes 0.0
        expected = (
            np.corrcoef(a[..., 0].ravel(), b[..., 0].ravel())[0, 1]
            + 0.0
            + np.corrcoef(a[..., 2].ravel(), b[..., 2].ravel())[0, 1]
        ) / 3
        assert cross_correlation(a, b) == pytest.approx(expected, abs=1e-12)

    def test_correlation_near_constant_large_image_matches_numpy(self):
        a = np.full((512, 512), 250, dtype=np.uint8)
        b = np.full((512, 512), 3, dtype=np.uint8)
        a[0, 0], a[5, 7], b[0, 0], b[100, 9] = 251, 249, 4, 2
        expected = float(np.corrcoef(a.ravel(), b.ravel())[0, 1])
        assert cross_correlation(a, b) == pytest.approx(expected, abs=1e-12)

    def test_correlation_single_pixel_is_zero(self):
        one = np.array([[7]], dtype=np.uint8)
        assert cross_correlation(one, one) == 0.0

    def test_entropy_pools_all_rgb_channels(self):
        img = np.zeros((1, 2, 3), dtype=np.uint8)
        img[0, 1] = 255  # 3 zeros + 3 x 255 -> exactly 1 bit
        assert shannon_entropy(img) == pytest.approx(1.0)

    def test_scaled_cover_metrics_use_cover_used(self, cfg):
        # BM-07: coins 246x300 forces 257x257; metrics must compare equal-size images.
        res = run_from_config(cfg, "aes")
        assert res.cover_used_rgb.shape == res.stego_rgb.shape == (257, 257, 3)
        assert res.metrics["mse"] == pytest.approx(mse(res.cover_used_rgb, res.stego_rgb))
        assert res.metrics["npcr_stego"] == pytest.approx(npcr(res.cover_used_rgb, res.stego_rgb))
        assert 9.5 < res.metrics["mse"] < 11.5  # 3-LSB regime of BM-01 (~10.5)

    def test_enc_metrics_use_truncated_view_not_padded_ciphertext(self, cfg):
        res = run_from_config(cfg, "3des")
        assert len(res.ciphertext) == 73808 and res.encrypted_view.size == 73800
        assert res.metrics["npcr_enc"] == pytest.approx(npcr(res.secret, res.encrypted_view))
        assert res.metrics["entropy_enc"] == pytest.approx(shannon_entropy(res.encrypted_view))

    def test_summary_aggregation(self):
        df = pd.DataFrame(
            {
                "cipher": ["aes", "aes", "chaotic"],
                "exact_recovery": [True, True, True],
                **{
                    k: [1.0, 3.0, 5.0]
                    for k in (
                        "mse", "psnr", "ssim", "enc_time_s", "npcr_enc", "uaci_enc",
                        "corr_enc", "entropy_stego", "entropy_enc", "npcr_stego",
                        "uaci_stego", "corr_stego",
                    )
                },
            }
        )
        out = run_benchmark.build_summary_dataframe(df, ["3des", "aes", "chaotic"])
        assert list(out["cipher"]) == ["aes", "chaotic"]  # missing cipher skipped
        aes = out.iloc[0]
        assert aes["n_images"] == 2 and aes["avg_mse"] == 2.0 and aes["std_mse"] == 1.0

    @pytest.mark.parametrize(
        "name,expected",
        [("benchmark_results.csv", "benchmark_summary_table2.csv"),
         ("run_a.csv", "run_a_summary_table2.csv")],
    )
    def test_summary_csv_name(self, name, expected):
        assert run_benchmark.summary_csv_name(name) == expected
