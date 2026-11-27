"""Shared building blocks for the four tabs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from src.ui.controller import (
    CIPHER_LABELS,
    CIPHER_ORDER,
    KEY_MODE_LABELS,
    KEY_MODE_PAPER,
    KEY_MODE_PASSPHRASE,
)
from src.ui.widgets import ScrollableFrame

if TYPE_CHECKING:
    from src.ui.app_window import CT204App

IMAGE_FILETYPES = [("Ảnh", "*.png *.jpg *.jpeg *.bmp"), ("Tất cả", "*.*")]
PNG_FILETYPES = [("PNG lossless", "*.png")]
LEFT_PANEL_WIDTH = 330


class TwoPaneTab(ttk.Frame):
    """Left scrollable control column + right scrollable result area."""

    def __init__(self, master: tk.Misc, app: CT204App) -> None:
        super().__init__(master, padding=(8, 8, 8, 4))
        self.app = app
        self.cfg = app.cfg
        self.left_scroll = ScrollableFrame(self, width=LEFT_PANEL_WIDTH, fit_width=True)
        self.right_scroll = ScrollableFrame(self)
        self.left_scroll.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        self.right_scroll.grid(row=0, column=1, sticky="nsew")
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.left = self.left_scroll.inner
        self.right = self.right_scroll.inner

    def section(self, title: str) -> ttk.LabelFrame:
        box = ttk.LabelFrame(self.left, text=title, padding=10)
        box.pack(fill="x", pady=(0, 8))
        return box


class KeySelector(ttk.Frame):
    """Cipher combobox + key mode radios + passphrase entry with a show/hide toggle."""

    def __init__(self, master: tk.Misc, *, default_cipher: str = "aes",
                 on_cipher_change=None) -> None:
        super().__init__(master, style="Plain.TFrame")
        self._label_to_name = {CIPHER_LABELS[n]: n for n in CIPHER_ORDER}
        self.cipher_var = tk.StringVar(value=CIPHER_LABELS[default_cipher])
        self.key_mode_var = tk.StringVar(value=KEY_MODE_PAPER)
        self.passphrase_var = tk.StringVar(value="")
        self._show = False
        self._on_cipher_change = on_cipher_change

        ttk.Label(self, text="Thuật toán:").pack(anchor="w")
        self.cipher_combo = ttk.Combobox(self, textvariable=self.cipher_var, state="readonly",
                                         values=[CIPHER_LABELS[n] for n in CIPHER_ORDER])
        self.cipher_combo.pack(fill="x", pady=(2, 8))
        self.cipher_combo.bind("<<ComboboxSelected>>", lambda _e: self._cipher_changed())

        ttk.Label(self, text="Chế độ khóa:").pack(anchor="w")
        for mode in (KEY_MODE_PAPER, KEY_MODE_PASSPHRASE):
            ttk.Radiobutton(self, text=KEY_MODE_LABELS[mode], value=mode,
                            variable=self.key_mode_var,
                            command=self._mode_changed).pack(anchor="w")
        row = ttk.Frame(self, style="Plain.TFrame")
        row.pack(fill="x", pady=(4, 0))
        self.pass_entry = ttk.Entry(row, textvariable=self.passphrase_var, show="•")
        self.pass_entry.pack(side="left", fill="x", expand=True)
        self.show_btn = ttk.Button(row, text="👁", width=3, command=self.toggle_show)
        self.show_btn.pack(side="left", padx=(4, 0))
        self._mode_changed()

    @property
    def cipher_name(self) -> str:
        return self._label_to_name[self.cipher_var.get()]

    def set_cipher(self, name: str) -> None:
        self.cipher_var.set(CIPHER_LABELS[name])
        self._cipher_changed()

    @property
    def key_mode(self) -> str:
        return self.key_mode_var.get()

    @property
    def passphrase(self) -> str | None:
        return self.passphrase_var.get() if self.key_mode == KEY_MODE_PASSPHRASE else None

    def set_key(self, key_mode: str, passphrase: str | None) -> None:
        self.key_mode_var.set(key_mode)
        self.passphrase_var.set(passphrase or "")
        self._mode_changed()

    def validate(self) -> str | None:
        """Vietnamese error message, or None when the key settings are usable."""
        if self.key_mode == KEY_MODE_PASSPHRASE and not self.passphrase_var.get().strip():
            return "Hãy nhập mật khẩu (passphrase) hoặc chọn chế độ “Chuẩn bài báo”."
        return None

    def toggle_show(self) -> None:
        self._show = not self._show
        self.pass_entry.configure(show="" if self._show else "•")
        self.show_btn.configure(text="🙈" if self._show else "👁")

    def _mode_changed(self) -> None:
        state = "normal" if self.key_mode == KEY_MODE_PASSPHRASE else "disabled"
        self.pass_entry.configure(state=state)
        self.show_btn.configure(state=state)

    def _cipher_changed(self) -> None:
        if self._on_cipher_change is not None:
            self._on_cipher_change(self.cipher_name)


def png_path(path: str) -> str:
    """Force the ``.png`` suffix on a user-chosen path (lossless stego only)."""
    from pathlib import Path

    p = Path(path)
    return str(p if p.suffix.lower() == ".png" else p.with_suffix(".png"))


def existing_dir(*candidates) -> str | None:
    from pathlib import Path

    for c in candidates:
        if c is not None and Path(c).is_dir():
            return str(c)
    return None
