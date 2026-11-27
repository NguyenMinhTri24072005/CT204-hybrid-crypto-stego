"""Tab 2 — Trích xuất, Giải mã & Phòng thí nghiệm Tấn công (Decrypt & Tamper Lab)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

import numpy as np

from src.pipeline import read_gray, read_rgb, save_gray_png
from src.ui.controller import (
    CIPHER_LABELS,
    TAMPER_MODES,
    DecryptWorkflowResult,
    EncryptWorkflowResult,
    HeaderInspection,
    build_wrong_key_cipher,
    compare_images,
    fmt_num,
    guess_cipher_from_filename,
    inspect_stego_header,
    run_decrypt_workflow,
    simulate_tamper,
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
from src.ui.widgets import Banner, ImagePreviewCard

if TYPE_CHECKING:
    from src.ui.app_window import CT204App

HEADER_FIELDS = (
    ("magic", "Magic"),
    ("version", "Version"),
    ("num_lsb", "num_lsb"),
    ("shape", "Secret Shape (H×W)"),
    ("ct_len", "Ciphertext (bytes)"),
    ("crc", "CRC-16 (Expected / Actual)"),
    ("status", "Trạng thái"),
)


class DecryptTab(TwoPaneTab):
    def __init__(self, master: tk.Misc, app: CT204App) -> None:
        super().__init__(master, app)
        self.original_stego: np.ndarray | None = None
        self.current_stego: np.ndarray | None = None
        self.reference_secret: np.ndarray | None = None
        self.source_label = ""
        self.tamper_note = ""
        self.last_result: DecryptWorkflowResult | None = None
        self._build_controls()
        self._build_results()
        self._update_buttons()

    # ------------------------------------------------------------------ controls
    def _build_controls(self) -> None:
        box = self.section("1. Nguồn ảnh Stego")
        ttk.Button(box, text="📂 Mở ảnh Stego (.png)...", command=self.open_stego).pack(fill="x")
        ttk.Button(box, text="📥 Lấy ảnh Stego vừa tạo từ Tab 1",
                   command=self.pull_from_encrypt).pack(fill="x", pady=(6, 0))
        ttk.Button(box, text="📂 Chọn ảnh Secret gốc để đối chiếu MSE/BER...",
                   command=self.choose_reference).pack(fill="x", pady=(6, 0))
        self.source_info = ttk.Label(box, text="Chưa nạp ảnh Stego.", style="Muted.TLabel",
                                     wraplength=290, justify="left")
        self.source_info.pack(anchor="w", pady=(6, 0))

        box = self.section("2. Header 16-byte (HCST Live Inspector)")
        self.header_labels: dict[str, ttk.Label] = {}
        grid = ttk.Frame(box, style="Plain.TFrame")
        grid.pack(fill="x")
        for i, (key, label) in enumerate(HEADER_FIELDS):
            ttk.Label(grid, text=label + ":", style="Muted.TLabel").grid(row=i, column=0, sticky="w",
                                                                       pady=1)
            value = ttk.Label(grid, text="—", style="Mono.TLabel")
            value.grid(row=i, column=1, sticky="w", padx=(8, 0), pady=1)
            self.header_labels[key] = value
        self.header_error = ttk.Label(box, text="", style="Bad.TLabel", wraplength=290,
                                      justify="left")
        self.header_error.pack(anchor="w", pady=(4, 0))

        box = self.section("3. Cấu hình Giải mã")
        self.key_selector = KeySelector(box, default_cipher="aes")
        self.key_selector.pack(fill="x")
        self.decrypt_btn = ttk.Button(box, text="🔓 Trích xuất & Giải mã", style="Primary.TButton",
                                      command=self.decrypt)
        self.decrypt_btn.pack(fill="x", pady=(10, 0))
        self.save_btn = ttk.Button(box, text="💾 Lưu ảnh Secret khôi phục (.png)...",
                                   command=self.save_recovered)
        self.save_btn.pack(fill="x", pady=(6, 0))

        box = self.section("4. Security & Tamper Demo Lab")
        self.tamper_buttons: list[ttk.Button] = []
        for text, cmd in (
            ("🔑 Thử Giải mã Sai Khóa", self.try_wrong_key),
            ("📷 Nén JPEG (Quality = 95)", lambda: self.apply_tamper("jpeg_q95")),
            ("⚡ Đảo 1 Bit Header", lambda: self.apply_tamper("flip_header_bit")),
            ("🔊 Đảo 1% Bit Payload", lambda: self.apply_tamper("flip_payload_bits")),
            ("📡 Nhiễu Kênh truyền (Gaussian σ=2)", lambda: self.apply_tamper("gaussian_noise")),
        ):
            btn = ttk.Button(box, text=text, command=cmd)
            btn.pack(fill="x", pady=(0, 4))
            self.tamper_buttons.append(btn)
        self.reset_btn = ttk.Button(box, text="↩ Khôi phục lại ảnh Stego gốc ban đầu",
                                    command=self.reset_stego)
        self.reset_btn.pack(fill="x", pady=(6, 0))

    def _build_results(self) -> None:
        ttk.Label(self.right, text="Kết quả Trích xuất & Giải mã", style="Section.TLabel").pack(
            anchor="w", pady=(0, 6))
        cards = ttk.Frame(self.right)
        cards.pack(fill="x")
        box = (270, 240)
        self.card_stego = ImagePreviewCard(cards, "Ảnh Stego đang kiểm tra", box=box)
        self.card_recovered = ImagePreviewCard(cards, "Ảnh Secret khôi phục", box=box)
        self.card_reference = ImagePreviewCard(cards, "Ảnh Secret gốc đối chiếu", box=box)
        for i, card in enumerate((self.card_stego, self.card_recovered, self.card_reference)):
            card.grid(row=0, column=i, padx=(0, 8), pady=(0, 8), sticky="n")
        self.banner = Banner(self.right, "Nạp một ảnh Stego rồi bấm “🔓 Trích xuất & Giải mã”.",
                             tone="info")
        self.banner.pack(fill="x", pady=(0, 8))
        details = ttk.Frame(self.right, style="Card.TFrame", padding=10)
        details.pack(fill="x")
        ttk.Label(details, text="Chi tiết kỹ thuật", style="CardTitle.TLabel").pack(anchor="w")
        self.details_label = ttk.Label(details, text="—", style="Mono.TLabel", justify="left",
                                       wraplength=800)
        self.details_label.pack(anchor="w", pady=(4, 0))

    def _set_action_buttons_disabled(self) -> None:
        self.decrypt_btn.configure(state="disabled")
        for btn in self.tamper_buttons:
            btn.configure(state="disabled")
        self.reset_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")

    def _update_buttons(self) -> None:
        has = self.current_stego is not None
        state = "normal" if has else "disabled"
        self.decrypt_btn.configure(state=state)
        for btn in self.tamper_buttons:
            btn.configure(state=state)
        self.reset_btn.configure(state="normal" if has and self.tamper_note else "disabled")
        recovered = self.last_result is not None and self.last_result.recovered is not None
        self.save_btn.configure(state="normal" if recovered else "disabled")

    # ------------------------------------------------------------------- inputs
    def load_stego(self, stego: np.ndarray, source: str, *, reference: np.ndarray | None = None,
                   keep_reference: bool = False) -> None:
        self.original_stego = np.ascontiguousarray(stego)
        self.current_stego = self.original_stego.copy()
        self.source_label = source
        self.tamper_note = ""
        if not keep_reference:
            self.reference_secret = reference
        self.last_result = None
        self.card_recovered.set_image(None, "")
        self._show_reference()
        self._refresh_stego()
        self.banner.set("Đã nạp ảnh Stego — bấm “🔓 Trích xuất & Giải mã”.", "info")
        self.details_label.configure(text="—")
        self._update_buttons()

    def receive_from_encrypt(self, res: EncryptWorkflowResult, *, key_mode: str,
                             passphrase: str | None) -> None:
        """Tab 1 → Tab 2 hand-off: stego, reference secret, cipher and key settings."""
        self.key_selector.set_cipher(res.cipher_name)
        self.key_selector.set_key(key_mode, passphrase)
        self.load_stego(res.stego_rgb, f"Từ Tab 1 — {CIPHER_LABELS[res.cipher_name]}",
                        reference=res.secret_gray)
        self.app.set_status("Đã nhận ảnh Stego + Secret gốc từ Tab 1.", tone="info")

    def pull_from_encrypt(self) -> None:
        tab = self.app.tab_encrypt
        if tab.result is None:
            self.app.show_error("Chưa có ảnh Stego", "Hãy chạy “▶ Mã hóa & Giấu tin” ở Tab 1 trước.")
            return
        tab.send_to_decrypt()

    def open_stego(self) -> None:
        results_single = Path(self.cfg["paths"]["results_dir"]) / "single"
        path = filedialog.askopenfilename(parent=self, title="Mở ảnh Stego (.png)",
                                          initialdir=existing_dir(results_single),
                                          filetypes=[("PNG", "*.png"), *IMAGE_FILETYPES])
        if path:
            self.open_stego_path(path)

    def open_stego_path(self, path: str | Path) -> None:
        path = Path(path)
        try:
            stego = read_rgb(path)
        except (OSError, ValueError) as exc:
            self.app.show_error("Không đọc được ảnh", str(exc))
            return
        guess = guess_cipher_from_filename(path)
        if guess is not None:
            self.key_selector.set_cipher(guess)
        reference = None
        note = ""
        info = inspect_stego_header(stego)
        candidate = path.parent / "secret.png"
        if candidate.is_file() and info.is_valid:
            try:
                ref = read_gray(candidate)
                if ref.shape == info.secret_shape:
                    reference, note = ref, " (tự động gắn secret.png cùng thư mục)"
            except (OSError, ValueError):
                pass
        self.load_stego(stego, f"{path.name}{note}", reference=reference)

    def set_reference_secret(self, ref_gray: np.ndarray | None) -> None:
        self.reference_secret = None if ref_gray is None else np.ascontiguousarray(ref_gray, dtype=np.uint8)
        self._show_reference()
        res = self.last_result
        if res is not None and res.display_image is not None:
            res.extra.pop("reference_shape_mismatch", None)
            if self.reference_secret is None:
                res.recovery_mse = None
                res.recovery_psnr = None
                res.bit_error_rate = None
                res.is_exact = None
            elif self.reference_secret.shape == res.display_image.shape:
                stats = compare_images(self.reference_secret, res.display_image)
                res.recovery_mse = stats["mse"]
                res.recovery_psnr = stats["psnr"]
                res.bit_error_rate = stats["bit_error_rate"]
                res.is_exact = stats["is_exact"] and res.success
            else:
                res.recovery_mse = None
                res.recovery_psnr = None
                res.bit_error_rate = None
                res.is_exact = None
                res.extra["reference_shape_mismatch"] = (
                    self.reference_secret.shape,
                    res.display_image.shape,
                )
            self.show_result(res)

    def choose_reference(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Chọn ảnh Secret gốc (xám)",
                                          filetypes=IMAGE_FILETYPES)
        if not path:
            return
        try:
            ref = read_gray(path)
        except (OSError, ValueError) as exc:
            self.app.show_error("Không đọc được ảnh", str(exc))
            return
        self.set_reference_secret(ref)

    def _show_reference(self) -> None:
        if self.reference_secret is None:
            self.card_reference.set_image(None, "Không có ảnh đối chiếu")
        else:
            h, w = self.reference_secret.shape
            self.card_reference.set_image(self.reference_secret, f"{h}×{w}")

    def _refresh_stego(self) -> None:
        stego = self.current_stego
        if stego is None:
            return
        h, w = stego.shape[:2]
        tag = f" — {self.tamper_note}" if self.tamper_note else ""
        self.card_stego.set_image(stego, f"{h}×{w}{tag}", tone="bad" if self.tamper_note else None)
        self.source_info.configure(text=f"Nguồn: {self.source_label}\nKích thước: {w}×{h} RGB")
        self.show_header(inspect_stego_header(stego))

    def show_header(self, info: HeaderInspection) -> None:
        values = {
            "magic": f"{info.magic_text!r}  ({info.magic_raw.hex(' ').upper()})" if info.magic_raw else "—",
            "version": "—" if info.version is None else str(info.version),
            "num_lsb": "—" if info.num_lsb is None else str(info.num_lsb),
            "shape": "—" if info.secret_shape is None else f"{info.secret_shape[0]}×{info.secret_shape[1]}",
            "ct_len": "—" if info.ciphertext_len is None else f"{info.ciphertext_len:,}",
            "crc": "—" if info.crc_expected is None
            else f"0x{info.crc_expected:04X} / 0x{info.crc_actual:04X}",
            "status": info.status_text,
        }
        for key, label in self.header_labels.items():
            label.configure(text=values[key], style="Mono.TLabel")
        self.header_labels["status"].configure(style="Ok.TLabel" if info.is_valid else "Bad.TLabel")
        if info.crc_expected is not None:
            self.header_labels["crc"].configure(style="Ok.TLabel" if info.crc_ok else "Bad.TLabel")
        self.header_error.configure(text=info.error_message or "")

    # ------------------------------------------------------------------ actions
    def _key_problem(self) -> str | None:
        if self.current_stego is None:
            return "Hãy nạp một ảnh Stego trước."
        return self.key_selector.validate()

    def decrypt(self) -> None:
        problem = self._key_problem()
        if problem:
            self.app.show_error("Chưa thể giải mã", problem)
            return
        ks = self.key_selector
        self._set_action_buttons_disabled()
        self.app.set_status(f"Đang trích xuất & giải mã bằng {CIPHER_LABELS[ks.cipher_name]}...")
        self.app.runner.submit(
            run_decrypt_workflow, self.current_stego, self.cfg, cipher_name=ks.cipher_name,
            key_mode=ks.key_mode, passphrase=ks.passphrase,
            reference_secret_gray=self.reference_secret,
            on_success=self.show_result, on_error=self._on_error)

    def try_wrong_key(self) -> None:
        if self.original_stego is not None and self.tamper_note:
            self.current_stego = self.original_stego.copy()
            self.tamper_note = ""
            self._refresh_stego()
        problem = self._key_problem()
        if problem:
            self.app.show_error("Chưa thể thử sai khóa", problem)
            return
        ks = self.key_selector
        try:
            cipher, desc = build_wrong_key_cipher(ks.cipher_name, self.cfg, key_mode=ks.key_mode,
                                                  passphrase=ks.passphrase)
        except ValueError as exc:
            self.app.show_error("Không tạo được khóa sai", str(exc))
            return
        self._set_action_buttons_disabled()
        self.app.set_status(f"Thử giải mã sai khóa: {desc}...")
        self.app.runner.submit(
            run_decrypt_workflow, self.current_stego, self.cfg, cipher=cipher,
            key_mode=ks.key_mode, reference_secret_gray=self.reference_secret,
            key_description=f"SAI KHÓA — {desc}",
            on_success=self.show_result, on_error=self._on_error)

    def apply_tamper(self, mode: str) -> None:
        if self.current_stego is None:
            return
        try:
            tampered, note = simulate_tamper(self.original_stego, mode)
        except (ValueError, RuntimeError) as exc:
            self.app.show_error("Mô phỏng tấn công thất bại", str(exc))
            return
        self.current_stego = tampered
        self.tamper_note = TAMPER_MODES[mode]
        self._refresh_stego()
        self.details_label.configure(text=note)
        self._update_buttons()
        self.app.set_status(f"Đã mô phỏng tấn công: {TAMPER_MODES[mode]} — đang thử giải mã...",
                            tone="warn")
        if self.key_selector.validate() is None:
            self.decrypt()

    def reset_stego(self) -> None:
        if self.original_stego is None:
            return
        self.current_stego = self.original_stego.copy()
        self.tamper_note = ""
        self.last_result = None
        self.card_recovered.set_image(None, "")
        self._refresh_stego()
        self.banner.set("Đã khôi phục ảnh Stego gốc ban đầu (trạng thái sạch).", "info")
        self.details_label.configure(text="—")
        self._update_buttons()
        self.app.set_status("Đã khôi phục ảnh Stego gốc.", tone="info")

    def _on_error(self, exc: BaseException, _tb: str) -> None:
        self._update_buttons()
        self.app.set_status(f"Lỗi khi giải mã: {exc}", tone="bad")
        self.app.show_error("Giải mã thất bại", str(exc))

    def show_result(self, res: DecryptWorkflowResult) -> None:
        """Render a decrypt result (main thread)."""
        self.last_result = res
        self._update_buttons()
        image = res.display_image
        if res.recovered is not None:
            caption = "Khôi phục" + (" — KHỚP ✅" if res.is_exact else "")
            tone = "ok" if res.is_exact else ("bad" if res.is_exact is False else None)
            self.card_recovered.set_title("Ảnh Secret khôi phục")
            self.card_recovered.set_image(image, caption, tone=tone)
        elif image is not None:
            self.card_recovered.set_title("Bản xem trước nhiễu thô (không unpad)")
            self.card_recovered.set_image(image, "Giải mã CBC thô — sai khóa ⇒ nhiễu tuyết", tone="bad")
        else:
            self.card_recovered.set_title("Ảnh Secret khôi phục")
            self.card_recovered.set_image(None, "Không trích xuất được payload", tone="bad")

        prefix = f"{res.key_description}\n" if res.key_description else ""
        if res.success and res.is_exact:
            text = (f"✅ KHÔI PHỤC HOÀN HẢO — MSE = {res.recovery_mse:.6f}, BER = "
                    f"{res.bit_error_rate:.2%}. Header CRC-16 hợp lệ, giải mã {CIPHER_LABELS[res.cipher_name]} "
                    "đúng từng bit.")
            tone = "ok"
        elif res.success and res.is_exact is None:
            text = ("✅ Trích xuất & giải mã thành công (không có ảnh gốc để đối chiếu MSE/BER).")
            tone = "ok"
        else:
            reason = {"header": "Header bị hỏng", "extract": "Không trích xuất được payload",
                      "decrypt": "Giải mã thất bại", "ok": "Ảnh khôi phục sai lệch"}[res.stage]
            text = f"❌ {reason}: {res.message}"
            tone = "bad"
        self.banner.set(prefix + text, tone)

        lines = [f"Thuật toán: {CIPHER_LABELS[res.cipher_name]}   |   Giai đoạn: {res.stage}"]
        if res.secret_shape is not None:
            lines.append(f"Secret {res.secret_shape[0]}×{res.secret_shape[1]}, "
                         f"{res.ciphertext_len:,} byte bản mã ở {res.num_lsb}-LSB")
        if res.dec_time_s is not None:
            lines.append(f"Thời gian giải mã: {res.dec_time_s * 1e6:,.1f} µs")
        if res.recovery_mse is not None:
            lines.append(f"So với ảnh gốc: MSE = {fmt_num(res.recovery_mse, 6)}, "
                         f"PSNR = {fmt_num(res.recovery_psnr, 3)} dB, BER = {res.bit_error_rate:.4%}")
        if "reference_shape_mismatch" in res.extra:
            ref_shape, img_shape = res.extra["reference_shape_mismatch"]
            lines.append(f"Ảnh đối chiếu {ref_shape} khác kích thước ảnh giải mã {img_shape} — bỏ qua MSE/BER.")
        if self.tamper_note:
            lines.append(f"Ảnh đang bị tấn công: {self.tamper_note}")
        self.details_label.configure(text="\n".join(lines))
        self.app.set_status(text.splitlines()[0][:160], tone=tone)

    def save_recovered(self) -> None:
        res = self.last_result
        if res is None or res.recovered is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Lưu ảnh Secret khôi phục", defaultextension=".png",
            filetypes=PNG_FILETYPES, initialfile=f"{res.cipher_name}_recovered.png",
            initialdir=existing_dir(get_default_export_dir()))
        if not path:
            return
        try:
            saved = save_gray_png(png_path(path), res.recovered)
        except (OSError, ValueError) as exc:
            self.app.show_error("Không lưu được ảnh", str(exc))
            return
        self.app.set_status(f"Đã lưu ảnh Secret khôi phục: {saved}", tone="ok")
