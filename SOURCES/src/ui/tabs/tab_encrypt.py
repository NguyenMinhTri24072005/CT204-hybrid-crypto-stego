"""Tab 1 — Mã hóa & Giấu tin (Encrypt & Embed)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Any

import numpy as np

from src.pipeline import read_gray, read_rgb, save_stego_png
from src.ui import plots
from src.ui.controller import (
    CIPHER_LABELS,
    KEY_MODE_LABELS,
    TABLE2_SECRET_SIZE,
    EncryptWorkflowResult,
    fmt_num,
    fmt_time_us,
    load_sample_cover,
    load_sample_secret,
    run_encrypt_workflow,
)
from src.ui.resources import get_default_export_dir
from src.ui.tabs.common import (
    IMAGE_FILETYPES,
    PNG_FILETYPES,
    KeySelector,
    TwoPaneTab,
    existing_dir,
    png_path,
)
from src.ui.widgets import ImagePreviewCard, KpiBadgeRow, MatplotlibCard, StyledTreeview

if TYPE_CHECKING:
    from src.ui.app_window import CT204App

SIZE_ORIGINAL = "Giữ nguyên gốc (246×300 — Hình 4 & 5 bài báo)"
SIZE_TABLE2 = "Chuẩn Bảng 2 1-LSB (Resize 156×156)"
SIZE_CUSTOM = "Tùy chỉnh (nhập H × W)"


class EncryptTab(TwoPaneTab):
    def __init__(self, master: tk.Misc, app: CT204App) -> None:
        super().__init__(master, app)
        self.cover_rgb: np.ndarray | None = None
        self.cover_name = ""
        self.secret_gray: np.ndarray | None = None
        self.secret_name = ""
        self.result: EncryptWorkflowResult | None = None

        self._build_controls()
        self._build_results()
        self.load_sample_cover()
        self.load_sample_secret()

    # ------------------------------------------------------------------ controls
    def _build_controls(self) -> None:
        box = self.section("1. Ảnh Phủ (Cover RGB)")
        row = ttk.Frame(box, style="Plain.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="📂 Chọn ảnh Cover...", command=self.choose_cover).pack(side="left")
        ttk.Button(row, text="🖼 Ảnh mẫu (cover.jpg)", command=self.load_sample_cover).pack(
            side="left", padx=(6, 0))
        self.normalize_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="Chuẩn hóa Cover về 256×256 (chuẩn bài báo)",
                        variable=self.normalize_var).pack(anchor="w", pady=(8, 0))
        self.cover_info = ttk.Label(box, text="", style="Muted.TLabel")
        self.cover_info.pack(anchor="w", pady=(4, 0))

        box = self.section("2. Ảnh Bí mật (Secret Grayscale)")
        row = ttk.Frame(box, style="Plain.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="📂 Chọn ảnh Secret...", command=self.choose_secret).pack(side="left")
        ttk.Button(row, text="🪙 Ảnh mẫu (coins 246×300)", command=self.load_sample_secret).pack(
            side="left", padx=(6, 0))
        ttk.Label(box, text="Chế độ kích thước Secret (BM-01):").pack(anchor="w", pady=(8, 2))
        self.size_var = tk.StringVar(value=SIZE_ORIGINAL)
        self.size_combo = ttk.Combobox(box, textvariable=self.size_var, state="readonly",
                                       values=[SIZE_ORIGINAL, SIZE_TABLE2, SIZE_CUSTOM])
        self.size_combo.pack(fill="x")
        self.size_combo.bind("<<ComboboxSelected>>", lambda _e: self._size_mode_changed())
        row = ttk.Frame(box, style="Plain.TFrame")
        row.pack(fill="x", pady=(6, 0))
        self.custom_h = tk.IntVar(value=128)
        self.custom_w = tk.IntVar(value=128)
        ttk.Label(row, text="H").pack(side="left")
        self.spin_h = ttk.Spinbox(row, from_=8, to=4096, width=6, textvariable=self.custom_h)
        self.spin_h.pack(side="left", padx=(4, 10))
        ttk.Label(row, text="W").pack(side="left")
        self.spin_w = ttk.Spinbox(row, from_=8, to=4096, width=6, textvariable=self.custom_w)
        self.spin_w.pack(side="left", padx=(4, 0))
        self.secret_info = ttk.Label(box, text="", style="Muted.TLabel")
        self.secret_info.pack(anchor="w", pady=(4, 0))
        self._size_mode_changed()

        box = self.section("3. Thuật toán & Khóa")
        self.key_selector = KeySelector(box, default_cipher="aes",
                                        on_cipher_change=self._cipher_changed)
        self.key_selector.pack(fill="x")
        self.cache_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text="Pre-cache mặt nạ Chaotic (BM-10)",
                        variable=self.cache_var).pack(anchor="w", pady=(8, 0))

        box = self.section("4. Hành động")
        self.run_btn = ttk.Button(box, text="▶ Mã hóa & Giấu tin", style="Primary.TButton",
                                  command=self.run)
        self.run_btn.pack(fill="x")
        self.save_btn = ttk.Button(box, text="💾 Lưu ảnh Stego (.png)...", command=self.save_stego,
                                   state="disabled")
        self.save_btn.pack(fill="x", pady=(6, 0))
        self.send_btn = ttk.Button(box, text="➡ Chuyển sang Tab Giải mã", command=self.send_to_decrypt,
                                   state="disabled")
        self.send_btn.pack(fill="x", pady=(6, 0))

    def _size_mode_changed(self) -> None:
        state = "normal" if self.size_var.get() == SIZE_CUSTOM else "disabled"
        self.spin_h.configure(state=state)
        self.spin_w.configure(state=state)

    def _cipher_changed(self, name: str) -> None:
        self.cache_var.set(name == "chaotic")

    def selected_secret_size(self) -> tuple[int, int] | None:
        mode = self.size_var.get()
        if mode == SIZE_TABLE2:
            return TABLE2_SECRET_SIZE
        if mode == SIZE_CUSTOM:
            try:
                h, w = int(self.custom_h.get()), int(self.custom_w.get())
            except (tk.TclError, ValueError) as exc:
                raise ValueError("Kích thước H × W phải là số nguyên dương.") from exc
            if h < 8 or w < 8 or h > 4096 or w > 4096:
                raise ValueError("Kích thước H × W phải nằm trong khoảng 8..4096.")
            return (h, w)
        return None

    # ------------------------------------------------------------------- results
    def _build_results(self) -> None:
        ttk.Label(self.right, text="Kết quả Mã hóa & Giấu tin", style="Section.TLabel").pack(
            anchor="w", pady=(0, 6))
        cards = ttk.Frame(self.right)
        cards.pack(fill="x")
        self.card_cover = ImagePreviewCard(cards, "1. Cover thực dùng", box=(185, 165))
        self.card_secret = ImagePreviewCard(cards, "2. Secret gốc (Gray)", box=(185, 165))
        self.card_cipher = ImagePreviewCard(cards, "3. Bản mã Ciphertext View", box=(185, 165))
        self.card_stego = ImagePreviewCard(cards, "4. Ảnh Stego (.png)", box=(185, 165))
        for i, card in enumerate((self.card_cover, self.card_secret, self.card_cipher, self.card_stego)):
            card.grid(row=0, column=i, padx=(0, 8), pady=(0, 8), sticky="n")
        self.stego_view_var = tk.StringVar(value="stego")
        ttk.Radiobutton(self.card_stego.footer, text="Xem ảnh Stego", value="stego",
                        variable=self.stego_view_var, command=self._refresh_stego_card).pack(anchor="w")
        ttk.Radiobutton(self.card_stego.footer, text="Bản đồ sai khác |Cover − Stego| × 50",
                        value="diff", variable=self.stego_view_var,
                        command=self._refresh_stego_card).pack(anchor="w")

        self.kpis = KpiBadgeRow(self.right)
        self.kpis.pack(fill="x", pady=(2, 6))
        self.kpis.set_items([("Trạng thái", "Chưa chạy", "neutral")])

        card = ttk.Frame(self.right, style="Card.TFrame", padding=8)
        card.pack(fill="x", pady=(0, 8))
        ttk.Label(card, text="Bảng chỉ số bảo mật kép (BM-08)", style="CardTitle.TLabel").pack(anchor="w")
        self.table = StyledTreeview(card, [
            ("group", "Nhóm đo", 250, "w"), ("npcr", "NPCR (%)", 110, "e"),
            ("uaci", "UACI (%)", 110, "e"), ("corr", "Corr", 110, "e"),
            ("entropy", "Entropy (bits)", 120, "e")], height=2)
        self.table.pack(fill="x", pady=(4, 0))

        self.hist_card = MatplotlibCard(self.right, figsize=(9.4, 2.6),
                                        title="Histogram 256-bin (gộp phẳng kênh RGB — BM-10)")
        self.hist_card.pack(fill="x")
        self.hist_card.show_message("Bấm “▶ Mã hóa & Giấu tin” để vẽ histogram.")

    # ------------------------------------------------------------------- inputs
    def _set_cover(self, img: np.ndarray, name: str) -> None:
        self.cover_rgb, self.cover_name = img, name
        h, w = img.shape[:2]
        self.cover_info.configure(text=f"{name}: {w}×{h} RGB")
        self.card_cover.set_image(img, f"{name} — {h}×{w} (chưa nhúng)")

    def _set_secret(self, img: np.ndarray, name: str) -> None:
        self.secret_gray, self.secret_name = img, name
        h, w = img.shape[:2]
        self.secret_info.configure(text=f"{name}: {h}×{w} gray")
        self.card_secret.set_image(img, f"{name} — {h}×{w}")

    def load_sample_cover(self) -> None:
        try:
            self._set_cover(load_sample_cover(self.cfg), "cover.jpg")
        except (OSError, ValueError) as exc:
            self.app.show_error("Không đọc được ảnh mẫu", str(exc))

    def load_sample_secret(self) -> None:
        try:
            self._set_secret(load_sample_secret(self.cfg), "coins")
        except (OSError, ValueError) as exc:
            self.app.show_error("Không đọc được ảnh mẫu", str(exc))

    def choose_cover(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Chọn ảnh Cover (RGB)",
                                          filetypes=IMAGE_FILETYPES)
        if path:
            try:
                self._set_cover(read_rgb(path), Path(path).name)
            except (OSError, ValueError) as exc:
                self.app.show_error("Không đọc được ảnh", str(exc))

    def choose_secret(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Chọn ảnh Secret (sẽ chuyển sang xám)",
                                          filetypes=IMAGE_FILETYPES)
        if path:
            try:
                self._set_secret(read_gray(path), Path(path).name)
            except (OSError, ValueError) as exc:
                self.app.show_error("Không đọc được ảnh", str(exc))

    # ------------------------------------------------------------------ actions
    def collect_params(self) -> dict[str, Any]:
        """Read every control on the main thread (the worker never touches Tk)."""
        if self.cover_rgb is None or self.secret_gray is None:
            raise ValueError("Hãy chọn đủ ảnh Cover và ảnh Secret.")
        problem = self.key_selector.validate()
        if problem:
            raise ValueError(problem)
        return dict(
            cover_rgb=self.cover_rgb, secret_gray=self.secret_gray, cfg=self.cfg,
            cipher_name=self.key_selector.cipher_name, key_mode=self.key_selector.key_mode,
            passphrase=self.key_selector.passphrase, cache_chaotic_mask=bool(self.cache_var.get()),
            normalize=bool(self.normalize_var.get()), secret_size=self.selected_secret_size(),
        )

    def run(self) -> None:
        try:
            params = self.collect_params()
        except ValueError as exc:
            self.app.show_error("Thiếu thông tin", str(exc))
            return
        label = CIPHER_LABELS[params["cipher_name"]]
        self.run_btn.configure(state="disabled")
        self.app.set_status(f"Đang mã hóa và nhúng tin bằng {label}...")
        cover, secret, cfg = params.pop("cover_rgb"), params.pop("secret_gray"), params.pop("cfg")
        self.app.runner.submit(run_encrypt_workflow, cover, secret, cfg, **params,
                               on_success=self.show_result, on_error=self._on_error)

    def _on_error(self, exc: BaseException, _tb: str) -> None:
        self.run_btn.configure(state="normal")
        self.app.set_status(f"Lỗi khi mã hóa: {exc}", tone="bad")
        self.app.show_error("Mã hóa thất bại", str(exc))

    def show_result(self, res: EncryptWorkflowResult) -> None:
        """Render a finished workflow (main thread)."""
        self.result = res
        self.run_btn.configure(state="normal")
        self.save_btn.configure(state="normal")
        self.send_btn.configure(state="normal")
        m = res.metrics
        ch, cw = res.cover_used_rgb.shape[:2]
        ih, iw = res.cover_input_shape[:2]
        cover_caption = f"{ch}×{cw}"
        if res.was_scaled_up:
            cover_caption += f" — Auto-scaled {ih}→{ch}" if ih == iw else f" — Auto-scaled từ {ih}×{iw}"
        self.card_cover.set_image(res.cover_used_rgb, cover_caption, tone="bad" if res.was_scaled_up else None)
        sh, sw = res.secret_gray.shape
        self.card_secret.set_image(res.secret_gray, f"{sh}×{sw}")
        self.card_cipher.set_image(res.encrypted_view,
                                   f"{res.ciphertext_len:,} byte (hiển thị {sh * sw:,} — BM-05)")
        self._refresh_stego_card()

        exact = res.is_exact
        self.kpis.set_items([
            ("Số bit LSB", f"k = {res.num_lsb}", "info"),
            ("Kích thước bản mã", f"{res.ciphertext_len:,} bytes", "neutral"),
            ("MSE", fmt_num(m["mse"]), "neutral"),
            ("PSNR (dB)", fmt_num(m["psnr"], 3), "neutral"),
            ("SSIM", fmt_num(m["ssim"], 5), "neutral"),
            ("EncTime", fmt_time_us(res.enc_time_s), "neutral"),
            ("Kiểm chứng vòng kín", "MSE = 0 ✅" if exact else "MSE ≠ 0 ❌", "ok" if exact else "bad"),
        ])
        self.table.set_rows([
            ("Bản mã (Secret vs Encrypted)", fmt_num(m["npcr_enc"]), fmt_num(m["uaci_enc"]),
             fmt_num(m["corr_enc"], 5), fmt_num(m["entropy_enc"])),
            ("Ảnh giấu tin (Cover vs Stego)", fmt_num(m["npcr_stego"]), fmt_num(m["uaci_stego"]),
             fmt_num(m["corr_stego"], 5), fmt_num(m["entropy_stego"])),
        ])
        self.hist_card.draw(lambda fig: plots.draw_triple_histograms(
            fig, res.cover_used_rgb, res.encrypted_view, res.stego_rgb))
        self.app.set_status(
            f"Hoàn tất {res.cipher_label} ({KEY_MODE_LABELS[res.key_mode]}): k = {res.num_lsb}, "
            f"PSNR = {fmt_num(m['psnr'], 3)} dB, khôi phục {'MSE = 0 ✅' if exact else 'LỖI ❌'}",
            tone="ok" if exact else "bad")

    def _refresh_stego_card(self) -> None:
        res = self.result
        if res is None:
            return
        h, w = res.stego_rgb.shape[:2]
        if self.stego_view_var.get() == "diff":
            changed = int(np.count_nonzero(res.diff_heatmap))
            self.card_stego.set_image(res.diff_heatmap,
                                      f"|Cover − Stego| × {res.diff_gain:g} — {changed:,} kênh đổi")
        else:
            self.card_stego.set_image(res.stego_rgb, f"{h}×{w} — {res.num_lsb}-LSB")

    def save_stego(self) -> None:
        if self.result is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Lưu ảnh Stego (PNG lossless)", defaultextension=".png",
            filetypes=PNG_FILETYPES, initialfile=f"{self.result.cipher_name}_stego.png",
            initialdir=existing_dir(get_default_export_dir()))
        if not path:
            return
        try:
            saved = save_stego_png(png_path(path), self.result.stego_rgb)
        except (OSError, ValueError) as exc:
            self.app.show_error("Không lưu được ảnh", str(exc))
            return
        self.app.set_status(f"Đã lưu ảnh Stego lossless: {saved}", tone="ok")

    def send_to_decrypt(self) -> None:
        if self.result is None:
            return
        self.app.tab_decrypt.receive_from_encrypt(
            self.result, key_mode=self.key_selector.key_mode,
            passphrase=self.key_selector.passphrase_var.get())
        self.app.select_tab("decrypt")
