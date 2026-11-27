"""Phase 3 tests: src/pipeline.py end-to-end (exact recovery, MSE == 0)."""

from __future__ import annotations

import copy

import cv2
import numpy as np
import pytest

from src.config import load_config
from src.crypto import CIPHER_NAMES, ciphertext_to_image_view, create_cipher
from src.pipeline import (
    hide,
    read_gray,
    read_rgb,
    reveal,
    run_from_config,
    run_pipeline,
    save_stego_png,
)
from src.stego.lsb import extract


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def secret(cfg) -> np.ndarray:
    return read_gray(cfg["secret"]["path"])


@pytest.fixture(scope="module")
def cover(cfg) -> np.ndarray:
    return read_rgb(cfg["paths"]["sample_dir"] / "cover.jpg", size=tuple(cfg["stego"]["cover_size"]))


def _mse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))


# ------------------------------------------------------------------------ sample data
def test_sample_images(secret, cover):
    assert secret.shape == (246, 300) and secret.dtype == np.uint8  # BM-01
    assert cover.shape == (256, 256, 3) and cover.dtype == np.uint8


# ------------------------------------------------------------------------- end-to-end
@pytest.mark.parametrize("name", CIPHER_NAMES)
def test_end_to_end_coins_via_png(cfg, secret, cover, name, tmp_path):
    cipher = create_cipher(name, cfg)
    res = run_pipeline(secret, cover, cipher, stego_path=tmp_path / f"stego_{name}.png")
    assert res.stego_path.is_file()
    assert res.is_exact and _mse(secret, res.recovered) == 0.0
    # 246x300 (+ padding) exceeds 3-LSB capacity of 256x256 -> scaled to 257x257 (BM-07)
    assert res.embed.was_scaled_up and res.embed.num_lsb == 3
    assert res.stego_rgb.shape == res.cover_used_rgb.shape == (257, 257, 3)
    assert np.array_equal(res.stego_rgb, res.embed.stego_rgb)  # PNG is lossless
    assert res.encrypted_view.shape == secret.shape
    expected_metric_keys = {
        "mse",
        "psnr",
        "ssim",
        "enc_time_s",
        "npcr_enc",
        "uaci_enc",
        "corr_enc",
        "entropy_enc",
        "npcr_stego",
        "uaci_stego",
        "corr_stego",
        "entropy_stego",
    }
    assert set(res.metrics) == expected_metric_keys
    assert res.enc_time_s == res.metrics["enc_time_s"] > 0.0


def test_compute_metrics_can_be_disabled(cfg, secret, cover):
    res = run_pipeline(secret, cover, create_cipher("aes", cfg), compute_metrics=False)
    assert res.is_exact
    assert res.metrics == {}
    assert res.enc_time_s > 0.0


@pytest.mark.parametrize("name", CIPHER_NAMES)
def test_end_to_end_table2_size_uses_one_lsb(cfg, secret, cover, name, tmp_path):
    small = cv2.resize(secret, (156, 156), interpolation=cv2.INTER_AREA)
    res = run_pipeline(small, cover, create_cipher(name, cfg), stego_path=tmp_path / "s.png")
    assert res.is_exact and _mse(small, res.recovered) == 0.0
    assert res.embed.num_lsb == 1 and not res.embed.was_scaled_up
    assert res.cover_used_rgb.shape == cover.shape


@pytest.mark.parametrize("name", CIPHER_NAMES)
@pytest.mark.parametrize("fill", [0, 255])
def test_constant_secret_roundtrip(cfg, cover, name, fill):
    flat = np.full((64, 80), fill, dtype=np.uint8)  # BM-05: all-black / all-white edge cases
    res = run_pipeline(flat, cover, create_cipher(name, cfg))
    assert res.is_exact


@pytest.mark.parametrize("name", CIPHER_NAMES)
def test_blind_reveal_from_file_with_fresh_cipher(cfg, secret, cover, name, tmp_path):
    _, emb = hide(secret, cover, create_cipher(name, cfg))
    path = save_stego_png(tmp_path / "only_this_file.png", emb.stego_rgb)
    recovered = reveal(read_rgb(path), create_cipher(name, cfg))  # receiver side
    assert np.array_equal(recovered, secret)


@pytest.mark.parametrize("name", CIPHER_NAMES)
def test_ciphertext_fully_embedded(cfg, secret, cover, name):
    ct, emb = hide(secret, cover, create_cipher(name, cfg))
    extracted, shape, _ = extract(emb.stego_rgb)
    assert extracted == ct and shape == secret.shape
    assert emb.ciphertext_len == len(ct)
    assert np.array_equal(ciphertext_to_image_view(ct, shape).reshape(-1), np.frombuffer(ct[: shape[0] * shape[1]], np.uint8))


def test_wrong_key_does_not_recover(cfg, secret, cover):
    _, emb = hide(secret, cover, create_cipher("aes", cfg))
    try:
        assert not np.array_equal(reveal(emb.stego_rgb, create_cipher("aes", cfg, seed_offset=1)), secret)
    except ValueError:
        pass  # wrong key usually breaks PKCS#7 padding

    _, emb = hide(secret, cover, create_cipher("chaotic", cfg))
    wrong = reveal(emb.stego_rgb, create_cipher("chaotic", cfg, seed_offset=1))
    assert not np.array_equal(wrong, secret)


def test_jpeg_compression_destroys_payload(cfg, secret, cover):
    _, emb = hide(secret, cover, create_cipher("aes", cfg))
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(emb.stego_rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
    jpeg = cv2.cvtColor(cv2.imdecode(buf, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    with pytest.raises(ValueError):
        reveal(jpeg, create_cipher("aes", cfg))


def test_reveal_plain_cover_fails(cfg, cover):
    with pytest.raises(ValueError):
        reveal(cover, create_cipher("aes", cfg))


# ------------------------------------------------------------------------------- I/O
@pytest.mark.parametrize("name", ["stego.jpg", "stego.jpeg", "stego.JPG", "stego.bmp", "stego"])
def test_save_rejects_non_png(tmp_path, name):
    with pytest.raises(ValueError):
        save_stego_png(tmp_path / name, np.zeros((8, 8, 3), np.uint8))
    assert not (tmp_path / name).exists()


def test_save_accepts_uppercase_png_and_creates_dirs(tmp_path):
    img = np.random.default_rng(0).integers(0, 256, (9, 11, 3), dtype=np.uint8)
    path = save_stego_png(tmp_path / "a" / "b" / "STEGO.PNG", img)
    assert np.array_equal(read_rgb(path), img)


def test_save_rejects_bad_array(tmp_path):
    with pytest.raises(ValueError):
        save_stego_png(tmp_path / "x.png", np.zeros((8, 8), np.uint8))


def test_rgb_bgr_boundary(tmp_path):
    img = np.zeros((2, 2, 3), np.uint8)
    img[..., 0] = 200  # pure red in RGB
    path = save_stego_png(tmp_path / "red.png", img)
    raw_bgr = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)
    assert raw_bgr[0, 0].tolist() == [0, 0, 200]
    assert read_rgb(path)[0, 0].tolist() == [200, 0, 0]


def test_unicode_and_space_path(tmp_path):
    img = np.random.default_rng(1).integers(0, 256, (5, 5, 3), dtype=np.uint8)
    path = save_stego_png(tmp_path / "thư mục ảnh" / "giấu tin.png", img)
    assert np.array_equal(read_rgb(path), img)


def test_read_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_rgb(tmp_path / "nope.png")


def test_read_resize(cfg):
    assert read_gray(cfg["secret"]["path"], size=(156, 156)).shape == (156, 156)
    assert read_rgb(cfg["paths"]["sample_dir"] / "cover.jpg", size=(128, 100)).shape == (128, 100, 3)


@pytest.mark.parametrize("bad", [np.zeros((4, 4, 3), np.uint8), np.zeros((4, 4), np.float32)])
def test_hide_rejects_bad_secret(cfg, cover, bad):
    with pytest.raises(ValueError):
        hide(bad, cover, create_cipher("aes", cfg))


# ---------------------------------------------------------------------- from config
@pytest.mark.parametrize("name", CIPHER_NAMES)
def test_run_from_config_defaults(cfg, name, tmp_path):
    res = run_from_config(cfg, name, stego_path=tmp_path / "s.png")
    assert res.is_exact and res.secret.shape == (246, 300)
    assert res.cipher_name == name


def test_run_from_config_secret_resize(cfg, tmp_path):
    cfg2 = copy.deepcopy(cfg)
    cfg2["secret"]["resize"] = [156, 156]
    res = run_from_config(cfg2, "chaotic", cache_chaotic_mask=True)
    assert res.is_exact and res.secret.shape == (156, 156) and res.embed.num_lsb == 1
    res2 = run_from_config(cfg, "aes", secret_size=(100, 120))
    assert res2.is_exact and res2.secret.shape == (100, 120)
