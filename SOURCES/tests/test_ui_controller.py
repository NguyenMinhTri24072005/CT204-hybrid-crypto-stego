"""Phase 6A tests: src/ui resources, controller (key modes, header inspector, tamper lab,
benchmark bundle), worker threading and a CT204App smoke/integration test."""

from __future__ import annotations

import shutil
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.crypto import create_cipher
from src.pipeline import read_gray, read_rgb
from src.ui import controller as ctl
from src.ui import resources
from src.ui.controller import (
    CIPHER_ORDER,
    KEY_MODE_PAPER,
    KEY_MODE_PASSPHRASE,
    PAPER_TABLE2_REFERENCE,
    TAMPER_MODES,
    build_ui_cipher,
    build_wrong_key_cipher,
    compute_diff_heatmap,
    inspect_stego_header,
    load_benchmark_bundle,
    mutate_passphrase,
    run_compare_workflow,
    run_decrypt_workflow,
    run_encrypt_workflow,
    simulate_tamper,
)

SOURCES = Path(__file__).resolve().parents[1]
SMALL = (64, 80)  # fast secret size for most tests


@pytest.fixture(scope="module")
def cfg():
    return resources.load_ui_config()


@pytest.fixture(scope="module")
def cover(cfg):
    return ctl.load_sample_cover(cfg)


@pytest.fixture(scope="module")
def secret(cfg):
    return ctl.load_sample_secret(cfg)


@pytest.fixture(scope="module")
def small_secret(secret):
    return ctl.resize_secret(secret, SMALL)


@pytest.fixture(scope="module")
def encrypted(cfg, cover, small_secret):
    """One clean encrypt result per cipher in passphrase mode."""
    return {
        name: run_encrypt_workflow(cover, small_secret, cfg, cipher_name=name,
                                   key_mode=KEY_MODE_PASSPHRASE, passphrase="ct204-demo")
        for name in CIPHER_ORDER
    }


# =============================================================== 1. resources.py
class TestResources:
    def test_dev_mode_root_is_sources(self):
        assert resources.is_frozen() is False
        root = resources.get_resource_root()
        assert root == SOURCES
        assert (root / "configs" / "default.yaml").is_file()

    def test_dev_export_dir_not_created(self):
        export = resources.get_default_export_dir()
        assert export == SOURCES / "results" / "ui_exports"

    def test_load_ui_config_matches_core_loader(self, cfg):
        core = load_config()
        assert cfg["paths"] == core["paths"]
        assert cfg["secret"]["path"] == core["secret"]["path"]
        assert cfg["crypto"] == core["crypto"]

    def test_missing_config(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resources.load_ui_config(tmp_path / "nope.yaml")

    def test_frozen_mode_uses_meipass(self, monkeypatch, tmp_path):
        bundle = tmp_path / "_MEI12345"
        (bundle / "configs").mkdir(parents=True)
        shutil.copy(SOURCES / "configs" / "default.yaml", bundle / "configs" / "default.yaml")
        (bundle / "data" / "sample").mkdir(parents=True)
        shutil.copy(SOURCES / "data" / "sample" / "cover.jpg", bundle / "data" / "sample")
        exe = tmp_path / "dist" / "CT204_CryptoStego.exe"
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
        monkeypatch.setattr(sys, "executable", str(exe))

        assert resources.is_frozen() is True
        assert resources.get_resource_root() == bundle.resolve()
        assert resources.get_default_export_dir() == exe.resolve().parent / "exports"
        cfg = resources.load_ui_config()
        assert cfg["paths"]["sample_dir"] == (bundle / "data" / "sample").resolve()
        assert cfg["paths"]["results_dir"] == (bundle / "results").resolve()
        assert cfg["secret"]["path"] == (bundle / "data" / "sample" / "secret.png").resolve()
        # sample cover read through the bundle; missing secret falls back to in-RAM coins
        assert ctl.load_sample_cover(cfg).shape == (256, 256, 3)
        assert ctl.load_sample_secret(cfg).shape == (246, 300)
        assert not (bundle / "data" / "sample" / "secret.png").exists()  # nothing written

    def test_frozen_requires_meipass(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        assert resources.is_frozen() is False


# ======================================================== 2. key modes (build_ui_cipher)
class TestKeyModes:
    @pytest.mark.parametrize("name", CIPHER_ORDER)
    def test_paper_default_matches_create_cipher(self, cfg, name):
        pt = bytes(range(256)) * 40
        ui = build_ui_cipher(name, cfg, key_mode=KEY_MODE_PAPER)
        assert ui.encrypt(pt) == create_cipher(name, cfg).encrypt(pt)

    @pytest.mark.parametrize("name", CIPHER_ORDER)
    def test_passphrase_roundtrip_exact(self, cfg, encrypted, name):
        enc = encrypted[name]
        assert enc.is_exact
        dec = run_decrypt_workflow(enc.stego_rgb, cfg, cipher_name=name,
                                   key_mode=KEY_MODE_PASSPHRASE, passphrase="ct204-demo",
                                   reference_secret_gray=enc.secret_gray)
        assert dec.success and dec.is_exact
        assert dec.recovery_mse == 0.0 and dec.bit_error_rate == 0.0
        assert np.array_equal(dec.recovered, enc.secret_gray)

    @pytest.mark.parametrize("name", CIPHER_ORDER)
    def test_passphrase_differs_from_paper_and_is_deterministic(self, cfg, name):
        pt = b"\x00" * 4096
        a = build_ui_cipher(name, cfg, key_mode=KEY_MODE_PASSPHRASE, passphrase="hello")
        b = build_ui_cipher(name, cfg, key_mode=KEY_MODE_PASSPHRASE, passphrase="hello")
        paper = build_ui_cipher(name, cfg)
        assert a.encrypt(pt) == b.encrypt(pt)
        assert a.encrypt(pt) != paper.encrypt(pt)

    def test_passphrase_domain_separated_per_cipher(self, cfg):
        aes = build_ui_cipher("aes", cfg, key_mode=KEY_MODE_PASSPHRASE, passphrase="same")
        des3 = build_ui_cipher("3des", cfg, key_mode=KEY_MODE_PASSPHRASE, passphrase="same")
        assert aes.key != des3.key[:16]

    def test_chaotic_passphrase_parameters(self, cfg):
        c = build_ui_cipher("chaotic", cfg, key_mode=KEY_MODE_PASSPHRASE, passphrase="pw",
                            cache_chaotic_mask=True)
        assert 0.1 <= c.x0 < 0.9 and c.r == 3.999 and 0 <= c.ecc_seed <= 0x7FFFFFFF
        assert c.cache_mask is True

    def test_3des_passphrase_skips_degenerate_keys(self, cfg, monkeypatch):
        real = ctl.derive_bytes
        degenerate = b"ABCDEFGH" * 2 + b"12345678"
        monkeypatch.setattr(ctl, "derive_bytes", lambda seed, n, label: degenerate
                            if label == "ui:3des:key:0" else real(seed, n, label))
        c = build_ui_cipher("3des", cfg, key_mode=KEY_MODE_PASSPHRASE, passphrase="pw")
        assert c.decrypt(c.encrypt(b"abc")) == b"abc"

    @pytest.mark.parametrize("bad", [None, "", "   "])
    def test_empty_passphrase_rejected(self, cfg, bad):
        with pytest.raises(ValueError, match="trống"):
            build_ui_cipher("aes", cfg, key_mode=KEY_MODE_PASSPHRASE, passphrase=bad)

    def test_invalid_mode_and_cipher(self, cfg):
        with pytest.raises(ValueError):
            build_ui_cipher("aes", cfg, key_mode="bogus")
        with pytest.raises(ValueError):
            build_ui_cipher("rsa", cfg)

    def test_mutate_passphrase_changes_one_char(self):
        for p in ("ct204-demo", "a", "Z9", "mật khẩu"):
            m = mutate_passphrase(p)
            assert len(m) == len(p) and m != p
            assert sum(x != y for x, y in zip(m, p)) == 1

    @pytest.mark.parametrize("name", CIPHER_ORDER)
    def test_one_char_wrong_passphrase_fails(self, cfg, encrypted, name):
        enc = encrypted[name]
        dec = run_decrypt_workflow(enc.stego_rgb, cfg, cipher_name=name,
                                   key_mode=KEY_MODE_PASSPHRASE,
                                   passphrase=mutate_passphrase("ct204-demo"),
                                   reference_secret_gray=enc.secret_gray)
        assert dec.is_exact is False
        assert (not dec.success) or dec.recovery_mse > 1000
        assert dec.recovery_mse is not None and dec.recovery_mse > 1000
        if name in ("3des", "aes") and not dec.success:
            assert dec.stage == "decrypt" and "PKCS#7" in dec.message
            assert dec.raw_corrupted_preview is not None
            assert dec.raw_corrupted_preview.shape == SMALL
            assert dec.raw_corrupted_preview.dtype == np.uint8

    @pytest.mark.parametrize("name", CIPHER_ORDER)
    @pytest.mark.parametrize("mode", [KEY_MODE_PAPER, KEY_MODE_PASSPHRASE])
    def test_wrong_key_cipher_helper(self, cfg, cover, small_secret, name, mode):
        pw = "ct204-demo" if mode == KEY_MODE_PASSPHRASE else None
        enc = run_encrypt_workflow(cover, small_secret, cfg, cipher_name=name, key_mode=mode,
                                   passphrase=pw)
        wrong, desc = build_wrong_key_cipher(name, cfg, key_mode=mode, passphrase=pw)
        assert desc
        dec = run_decrypt_workflow(enc.stego_rgb, cfg, cipher=wrong, key_mode=mode,
                                   reference_secret_gray=enc.secret_gray, key_description=desc)
        assert dec.is_exact is False and dec.key_description == desc
        assert dec.display_image is not None and dec.display_image.shape == SMALL

    def test_cli_results_single_decrypt_bit_exact(self, cfg):
        """paper_default must open the PNGs produced by scripts/run_single.py (MSE == 0)."""
        single = Path(cfg["paths"]["results_dir"]) / "single"
        if not (single / "secret.png").is_file():
            pytest.skip("results/single not generated")
        reference = read_gray(single / "secret.png")
        for name in CIPHER_ORDER:
            stego = read_rgb(single / f"{name}_stego.png")
            dec = run_decrypt_workflow(stego, cfg, cipher_name=name, key_mode=KEY_MODE_PAPER,
                                       reference_secret_gray=reference)
            assert dec.success and dec.is_exact, name


# ================================================================ encrypt workflow
class TestEncryptWorkflow:
    def test_scaled_coins_case(self, cfg, cover, secret):
        res = run_encrypt_workflow(cover, secret, cfg, cipher_name="aes")
        assert res.was_scaled_up and res.num_lsb == 3
        assert res.cover_used_rgb.shape == res.stego_rgb.shape == (257, 257, 3)
        assert res.diff_heatmap.shape == res.stego_rgb.shape
        assert res.is_exact and set(res.metrics) >= {"mse", "psnr", "ssim", "npcr_enc", "entropy_stego"}

    def test_table2_size_and_cover_normalisation(self, cfg, cover, secret):
        big_cover = np.repeat(np.repeat(cover, 2, axis=0), 2, axis=1)  # 512×512
        res = run_encrypt_workflow(big_cover, secret, cfg, cipher_name="chaotic",
                                   cache_chaotic_mask=True, secret_size=(156, 156))
        assert res.cover_input_shape == (512, 512, 3)
        assert res.cover_used_rgb.shape == (256, 256, 3) and res.num_lsb == 1
        assert 0.45 < res.metrics["mse"] < 0.55

    def test_no_normalisation_keeps_cover(self, cfg, cover, small_secret):
        odd = cover[:200, :230]
        res = run_encrypt_workflow(odd, small_secret, cfg, normalize=False)
        assert res.cover_used_rgb.shape == (200, 230, 3)

    def test_diff_heatmap(self):
        a = np.zeros((4, 4, 3), np.uint8)
        b = a.copy()
        b[0, 0, 0], b[1, 1, 1], b[2, 2, 2] = 1, 3, 9
        h = compute_diff_heatmap(a, b, gain=50)
        assert h.dtype == np.uint8 and h[0, 0, 0] == 50 and h[1, 1, 1] == 150 and h[2, 2, 2] == 255
        assert compute_diff_heatmap(b, a)[0, 0, 0] == 50  # symmetric, no uint8 underflow
        with pytest.raises(ValueError):
            compute_diff_heatmap(a, b[:3])


# ========================================================= 3. header inspector & tamper
class TestHeaderAndTamper:
    @pytest.mark.parametrize("name", CIPHER_ORDER)
    def test_clean_header_valid(self, encrypted, name):
        enc = encrypted[name]
        info = inspect_stego_header(enc.stego_rgb)
        assert info.is_valid and info.error_message is None and info.crc_ok
        assert info.magic_raw == b"HCST" and info.magic_text == "HCST" and info.version == 1
        assert info.num_lsb == enc.num_lsb and info.secret_shape == SMALL
        assert info.ciphertext_len == enc.ciphertext_len
        assert "HỢP LỆ" in info.status_text

    def test_random_image_invalid_magic(self):
        img = np.random.default_rng(1).integers(0, 256, (64, 64, 3), dtype=np.uint8)
        info = inspect_stego_header(img)
        assert info.is_valid is False and "Magic" in info.error_message
        assert info.secret_shape is None and "LỖI" in info.status_text

    @pytest.mark.parametrize("img", [np.zeros((5, 5, 3), np.uint8), np.zeros((64, 64, 3), np.float32)])
    def test_small_or_wrong_dtype_never_raises(self, img):
        assert inspect_stego_header(img).is_valid is False

    def test_capacity_overflow_reported(self, encrypted):
        cropped = encrypted["aes"].stego_rgb[:2]  # header intact, payload cut off
        info = inspect_stego_header(cropped)
        assert info.is_valid is False and "sức chứa" in info.error_message

    def test_flip_header_bit_crc(self, encrypted):
        tampered, note = simulate_tamper(encrypted["aes"].stego_rgb, "flip_header_bit")
        info = inspect_stego_header(tampered)
        assert info.is_valid is False and "CRC" in info.error_message
        assert info.magic_raw == b"HCST"  # magic untouched, only the CRC catches it
        assert info.crc_expected != info.crc_actual and "CRC" in note
        diff = np.flatnonzero(tampered.reshape(-1) != encrypted["aes"].stego_rgb.reshape(-1))
        assert diff.tolist() == [ctl.HEADER_TAMPER_BIT]

    @pytest.mark.parametrize("name", CIPHER_ORDER)
    def test_jpeg_q95_breaks_decryption(self, cfg, encrypted, name):
        tampered, note = simulate_tamper(encrypted[name].stego_rgb, "jpeg_q95")
        assert "JPEG" in note
        dec = run_decrypt_workflow(tampered, cfg, cipher_name=name, key_mode=KEY_MODE_PASSPHRASE,
                                   passphrase="ct204-demo")
        assert dec.success is False and dec.stage in ("header", "extract")

    @pytest.mark.parametrize("name", CIPHER_ORDER)
    @pytest.mark.parametrize("mode", ["flip_payload_bits", "gaussian_noise"])
    def test_payload_and_noise_detected(self, cfg, encrypted, name, mode):
        enc = encrypted[name]
        tampered, _ = simulate_tamper(enc.stego_rgb, mode)
        dec = run_decrypt_workflow(tampered, cfg, cipher_name=name, key_mode=KEY_MODE_PASSPHRASE,
                                   passphrase="ct204-demo", reference_secret_gray=enc.secret_gray)
        assert (not dec.success) or dec.is_exact is False
        if mode == "flip_payload_bits":
            assert inspect_stego_header(tampered).is_valid  # header passes, payload is wrong

    def test_flip_payload_fraction(self, encrypted):
        enc = encrypted["chaotic"]
        tampered, _ = simulate_tamper(enc.stego_rgb, "flip_payload_bits")
        diff = (tampered ^ enc.stego_rgb).reshape(-1)
        assert not diff[: ctl.HEADER_BITS].any() and set(np.unique(diff)) <= {0, 1}
        n_used = -(-8 * enc.ciphertext_len // enc.num_lsb)
        assert int(diff.sum()) == max(1, round(n_used * 0.01))

    @pytest.mark.parametrize("mode", list(TAMPER_MODES))
    def test_tamper_is_copy_and_deterministic(self, encrypted, mode):
        stego = encrypted["aes"].stego_rgb
        before = stego.copy()
        a, _ = simulate_tamper(stego, mode)
        b, _ = simulate_tamper(stego, mode)
        assert np.array_equal(stego, before) and not np.shares_memory(a, stego)
        assert np.array_equal(a, b) and a.shape == stego.shape and a.dtype == np.uint8
        assert not np.array_equal(a, stego)

    def test_unknown_tamper_mode(self, encrypted):
        with pytest.raises(ValueError):
            simulate_tamper(encrypted["aes"].stego_rgb, "laser")
        assert ctl.simulate_attack is simulate_tamper

    def test_decrypt_reference_shape_mismatch(self, cfg, encrypted):
        enc = encrypted["aes"]
        dec = run_decrypt_workflow(enc.stego_rgb, cfg, cipher_name="aes",
                                   key_mode=KEY_MODE_PASSPHRASE, passphrase="ct204-demo",
                                   reference_secret_gray=np.zeros((10, 10), np.uint8))
        assert dec.success and dec.is_exact is None and "reference_shape_mismatch" in dec.extra


# ======================================================== compare + export
class TestCompare:
    def test_compare_three_ciphers(self, cfg, cover, secret, tmp_path):
        res = run_compare_workflow(cover, secret, cfg, secret_size=(156, 156))
        assert list(res.results) == list(CIPHER_ORDER)
        assert list(res.table.columns) == list(ctl.COMPARE_COLUMNS)
        assert (res.table["Khôi phục (MSE=0)"] == "✅").all()
        assert res.table["num_lsb"].tolist() == [1, 1, 1]
        assert res.table["Tăng tốc so với 3DES (×)"].iloc[0] == pytest.approx(1.0)
        paths = ctl.export_compare_bundle(res, tmp_path / "export")
        names = {p.name for p in paths}
        assert {"fig4_cover_secret_histograms.png", "fig5_comparison_grid.png",
                "compare_metrics.csv", "aes_stego.png", "chaotic_recovered.png"} <= names
        assert all(p.is_file() and p.stat().st_size > 0 for p in paths)
        df = pd.read_csv(tmp_path / "export" / "compare_metrics.csv")
        assert df["exact_recovery"].all() and len(df) == 3


# =============================================================== 4. benchmark bundle
class TestBenchmarkBundle:
    @pytest.fixture(scope="class")
    def bundle(self):
        summary = SOURCES / "results" / ctl.SUMMARY_CSV
        if not summary.is_file():
            pytest.skip("results/benchmark_summary_table2.csv not generated")
        return load_benchmark_bundle()

    def test_summary_rows_match_paper_keys(self, bundle):
        assert bundle.ciphers == list(CIPHER_ORDER)
        assert set(bundle.ciphers) == set(PAPER_TABLE2_REFERENCE)
        for ref in PAPER_TABLE2_REFERENCE.values():
            assert {k for k, _ in ctl.TABLE2_METRICS} == set(ref)

    def test_comparison_table(self, bundle):
        comp = bundle.comparison_table()
        assert len(comp) == 3 * len(ctl.TABLE2_METRICS)
        aes_psnr = comp[(comp.cipher == "aes") & (comp.metric == "psnr")].iloc[0]
        assert aes_psnr.paper == PAPER_TABLE2_REFERENCE["aes"]["psnr"]
        assert aes_psnr.delta == pytest.approx(aes_psnr.ours - aes_psnr.paper)
        assert abs(aes_psnr.delta) < 0.5

    def test_overview_and_filters(self, bundle):
        ov = bundle.overview()
        if bundle.details is None:
            pytest.skip("details CSV absent")
        assert ov["n_runs"] == len(bundle.details) and ov["exact_rate"] == 1.0
        berry_test = bundle.filter_details("test", "berry")
        assert set(berry_test["split"]) == {"test"} and set(berry_test["class_name"]) == {"berry"}
        ours = bundle.ours(berry_test)
        assert set(ours) == set(CIPHER_ORDER)

    def test_summary_only_bundle(self, tmp_path):
        src = SOURCES / "results" / ctl.SUMMARY_CSV
        if not src.is_file():
            pytest.skip("summary CSV absent")
        shutil.copy(src, tmp_path / ctl.SUMMARY_CSV)
        b = load_benchmark_bundle(tmp_path)
        assert b.details is None and b.details_path is None
        assert b.filter_details("train").empty
        assert b.overview()["n_images"] > 0 and len(b.comparison_table()) == 27

    def test_errors(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_benchmark_bundle(tmp_path)
        pd.DataFrame({"x": [1]}).to_csv(tmp_path / ctl.SUMMARY_CSV, index=False)
        with pytest.raises(ValueError, match="cipher"):
            load_benchmark_bundle(tmp_path)


# ====================================================== matplotlib usage rule (spec §4.1)
def test_ui_package_never_uses_pyplot():
    """Spec §4.1: no pyplot import and no backend switching anywhere in src/ui (AST check)."""
    import ast

    for path in (SOURCES / "src" / "ui").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all("pyplot" not in a.name for a in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert "pyplot" not in (node.module or ""), path
                assert all(a.name != "pyplot" for a in node.names), path
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                is_use = (node.func.attr == "use" and isinstance(node.func.value, ast.Name)
                          and node.func.value.id == "matplotlib")
                assert not is_use, path


# ============================================================ worker + Tk smoke tests
_SHARED_TK: list = []


def _shared_tk():
    """One Tk interpreter for the whole session.

    Creating/destroying several ``tk.Tk()`` in one process is unreliable on Windows
    (intermittent "Can't find a usable init.tcl"), so every window under test is a
    ``Toplevel`` of this single root. Skips only when no display is available.
    """
    tk = pytest.importorskip("tkinter")
    if not _SHARED_TK:
        try:
            root = tk.Tk()
        except tk.TclError as exc:  # headless Linux without a display
            pytest.skip(f"Tk not available: {exc}")
        root.withdraw()
        _SHARED_TK.append(root)
    return _SHARED_TK[0]


def _tk_root():
    import tkinter as tk

    top = tk.Toplevel(_shared_tk())
    top.withdraw()
    return top


def _pump(root, runner, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    root.update()
    while runner.busy:
        if time.monotonic() > deadline:
            raise TimeoutError("background task did not finish")
        root.update()
        time.sleep(0.01)
    root.update()


class TestWorker:
    def test_callbacks_run_on_main_thread(self):
        from src.ui.worker import TaskRunner

        root = _tk_root()
        try:
            busy_log: list[bool] = []
            runner = TaskRunner(root, on_busy_change=busy_log.append)
            seen: dict[str, object] = {}

            def work(x):
                seen["worker_thread"] = threading.current_thread()
                return x * 2

            def done(value):
                seen["value"] = value
                seen["callback_thread"] = threading.current_thread()

            def failed(exc, tb):
                seen["error"] = (type(exc).__name__, "boom" in tb)

            def boom():
                raise RuntimeError("boom")

            runner.submit(work, 21, on_success=done)
            runner.submit(boom, on_error=failed)
            _pump(root, runner)
            assert seen["value"] == 42
            assert seen["callback_thread"] is threading.main_thread()
            assert seen["worker_thread"] is not threading.main_thread()
            assert seen["error"] == ("RuntimeError", True)
            assert busy_log == [True, False] and runner.busy is False
            runner.shutdown()
            with pytest.raises(RuntimeError):
                runner.submit(work, 1)
        finally:
            root.destroy()

    def test_shutdown_suppresses_late_callbacks(self):
        from src.ui.worker import TaskRunner

        root = _tk_root()
        try:
            runner = TaskRunner(root, poll_ms=200)
            called: list[int] = []
            gate = threading.Event()

            def slow_work():
                gate.wait(timeout=2.0)
                return 99

            thread = runner.submit(slow_work, on_success=called.append)
            runner.shutdown()
            gate.set()
            thread.join(timeout=2.0)
            runner._poll()  # even if a scheduled poll fires around shutdown, callbacks stay silent
            assert called == []
        finally:
            root.destroy()


class TestAppSmoke:
    def test_create_and_destroy(self, cfg):
        from src.ui.app_window import CT204App, WINDOW_TITLE

        root = _tk_root()
        try:
            app = CT204App(root, cfg, quiet_dialogs=True)
            root.update_idletasks()
            assert root.title() == WINDOW_TITLE
            assert len(app.notebook.tabs()) == 4
            assert app.tab_encrypt.cover_rgb is not None and app.tab_encrypt.secret_gray is not None
            assert "Sẵn sàng" in app.status_label.cget("text")
        finally:
            root.destroy()

    def test_end_to_end_through_widgets(self, cfg, tmp_path):
        """Drive the real tabs: encrypt (passphrase) → Tab 2 decrypt → tamper → reset →
        wrong key → compare → benchmark dashboard."""
        from src.ui.app_window import CT204App

        root = _tk_root()
        try:
            app = CT204App(root, cfg, quiet_dialogs=True)
            enc = app.tab_encrypt
            enc.key_selector.set_cipher("aes")
            enc.key_selector.set_key(KEY_MODE_PASSPHRASE, "")
            enc.run()  # empty passphrase -> friendly error, nothing submitted
            assert app.last_dialog and app.last_dialog[0] == "error" and not app.runner.busy

            enc.key_selector.set_key(KEY_MODE_PASSPHRASE, "ct204-demo")
            enc.size_var.set("Chuẩn Bảng 2 1-LSB (Resize 156×156)")
            enc.run()
            _pump(root, app.runner)
            assert enc.result is not None and enc.result.is_exact and enc.result.num_lsb == 1
            assert str(enc.save_btn.cget("state")) == "normal"
            enc.stego_view_var.set("diff")
            enc._refresh_stego_card()
            assert enc.card_stego.array is enc.result.diff_heatmap
            assert any("MSE = 0" in v for v in enc.kpis.values())

            enc.send_to_decrypt()
            dec = app.tab_decrypt
            assert app.notebook.select() == str(dec)
            assert dec.reference_secret is not None and dec.key_selector.cipher_name == "aes"
            assert dec.header_labels["status"].cget("text").startswith("HỢP LỆ")
            dec.decrypt()
            _pump(root, app.runner)
            assert dec.last_result.success and dec.last_result.is_exact
            assert dec.banner.tone == "ok"

            dec.apply_tamper("flip_header_bit")
            _pump(root, app.runner)
            assert dec.banner.tone == "bad" and dec.last_result.stage == "header"
            assert dec.header_labels["status"].cget("text").startswith("LỖI")
            dec.reset_stego()
            assert np.array_equal(dec.current_stego, dec.original_stego)

            dec.try_wrong_key()
            _pump(root, app.runner)
            assert dec.last_result.is_exact is False and dec.banner.tone == "bad"
            assert dec.card_recovered.array is not None  # noisy preview shown

            dec.apply_tamper("jpeg_q95")
            _pump(root, app.runner)
            assert dec.last_result.success is False

            # Pressing "Wrong Key" directly after a destructive tamper (without manual reset)
            # must auto-restore the clean stego so the demo shows the wrong-key failure, not JPEG/CRC.
            dec.try_wrong_key()
            _pump(root, app.runner)
            assert dec.header_labels["status"].cget("text").startswith("HỢP LỆ")
            assert dec.last_result.stage == "decrypt" and dec.banner.tone == "bad"
            assert dec.card_recovered.array is not None

            # Attaching/clearing reference secret after decryption immediately refreshes MSE/BER.
            saved_ref = dec.reference_secret
            dec.load_stego(enc.result.stego_rgb, "no-ref-yet", reference=None)
            dec.decrypt()
            _pump(root, app.runner)
            assert dec.last_result.success and dec.last_result.is_exact is None
            dec.set_reference_secret(saved_ref)
            assert dec.last_result.is_exact is True and dec.last_result.recovery_mse == 0.0
            assert "KHÔI PHỤC HOÀN HẢO" in dec.banner.cget("text")

            cmp_tab = app.tab_compare
            cmp_tab.preset_var.set("156×156 — Bảng 2 (1-LSB)")
            cmp_tab.run()
            _pump(root, app.runner)
            assert cmp_tab.result is not None and len(cmp_tab.table.rows()) == 3
            cmp_tab.view_var.set("speed")
            cmp_tab.redraw()

            # Export bundle on the background worker while TkAgg is active on the main thread.
            export_dir = tmp_path / "ui_export_worker"
            app.runner.submit(ctl.export_compare_bundle, cmp_tab.result, export_dir,
                              on_success=cmp_tab._exported, on_error=cmp_tab._export_failed)
            _pump(root, app.runner)
            assert (export_dir / "fig5_comparison_grid.png").is_file()

            bench = app.tab_benchmark
            app.select_tab("benchmark")  # triggers lazy CSV loading on the worker
            _pump(root, app.runner, timeout=120)
            if bench.bundle is not None:
                assert len(bench.table.rows()) == len(ctl.TABLE2_METRICS)
                for chart in ("Phân bố PSNR / SSIM / Entropy Stego theo 5 lớp ảnh",
                              "Phân bố thời gian mã hóa EncTime (µs) của 3 thuật toán"):
                    bench.chart_var.set(chart)
                    bench.class_var.set("bird")
                    bench.refresh()
                root.update()
        finally:
            app.close()
