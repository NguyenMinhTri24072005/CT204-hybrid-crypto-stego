"""Main window ``CT204App``: header banner, 4-tab ``ttk.Notebook`` and a status bar."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from src.ui.resources import CONFIG_RELATIVE, is_frozen, load_ui_config
from src.ui.tabs.tab_benchmark import BenchmarkTab
from src.ui.tabs.tab_compare import CompareTab
from src.ui.tabs.tab_decrypt import DecryptTab
from src.ui.tabs.tab_encrypt import EncryptTab
from src.ui.theme import COLORS, FONTS, apply_theme, enable_windows_dpi_awareness
from src.ui.worker import TaskRunner

WINDOW_TITLE = "CT204 — Hybrid Crypto-Steganography Framework (3DES · AES · Chaotic + Multi-LSB)"
DEFAULT_SIZE = (1360, 840)
MIN_SIZE = (1060, 680)
STATUS_TONES = {"info": COLORS["text"], "ok": COLORS["ok"], "bad": COLORS["bad"],
                "warn": COLORS["warn"]}


class CT204App:
    def __init__(self, root: tk.Tk | tk.Toplevel, cfg: dict[str, Any] | None = None, *,
                 quiet_dialogs: bool = False) -> None:
        self.root = root
        self.cfg = cfg if cfg is not None else load_ui_config()
        self.quiet_dialogs = quiet_dialogs
        self.colors = COLORS
        self.last_dialog: tuple[str, str, str] | None = None
        self.style = apply_theme(root)

        root.title(WINDOW_TITLE)
        root.minsize(*MIN_SIZE)
        self._center_window()

        self._build_header()
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(6, 0))
        self._build_status_bar()
        self.runner = TaskRunner(root, on_busy_change=self._on_busy)

        self.tab_encrypt = EncryptTab(self.notebook, self)
        self.tab_decrypt = DecryptTab(self.notebook, self)
        self.tab_compare = CompareTab(self.notebook, self)
        self.tab_benchmark = BenchmarkTab(self.notebook, self)
        self.tabs = {"encrypt": self.tab_encrypt, "decrypt": self.tab_decrypt,
                     "compare": self.tab_compare, "benchmark": self.tab_benchmark}
        self.notebook.add(self.tab_encrypt, text="🔐 1. Mã hóa & Giấu tin")
        self.notebook.add(self.tab_decrypt, text="🔓 2. Giải mã & Tamper Lab")
        self.notebook.add(self.tab_compare, text="⚖ 3. So sánh 3 Thuật toán")
        self.notebook.add(self.tab_benchmark, text="📊 4. Dashboard 8.000 ảnh")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        root.protocol("WM_DELETE_WINDOW", self.close)

        mode = " (.exe)" if is_frozen() else ""
        self.set_status(f"Sẵn sàng — Đã nạp cấu hình {CONFIG_RELATIVE.as_posix()}{mode}")

    # ----------------------------------------------------------------------- layout
    def _center_window(self) -> None:
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w = min(DEFAULT_SIZE[0], max(MIN_SIZE[0], sw - 40))
        h = min(DEFAULT_SIZE[1], max(MIN_SIZE[1], sh - 80))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 20)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_header(self) -> None:
        header = tk.Frame(self.root, background=COLORS["navy"], padx=16, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="Hybrid Crypto-Steganography Framework for Secure Image Transfer",
                 background=COLORS["navy"], foreground="white", font=FONTS["title"]).pack(anchor="w")
        tk.Label(header, text="CT204 — An toàn Thông tin · Tái hiện Raut et al., ICITSC 2025 · "
                 "3DES-192 · AES-128 · Chaotic (Logistic + ECC) + Multi-LSB · Offline 100%",
                 background=COLORS["navy"], foreground=COLORS["header_sub"],
                 font=FONTS["subtitle"]).pack(anchor="w")

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self.root, background=COLORS["card"], highlightbackground=COLORS["border"],
                       highlightthickness=1, padx=10, pady=4)
        bar.pack(fill="x", side="bottom")
        self.status_label = tk.Label(bar, text="", anchor="w", background=COLORS["card"],
                                     foreground=COLORS["text"], font=FONTS["body"])
        self.status_label.pack(side="left", fill="x", expand=True)
        # shown only while a background task runs (an idle indeterminate bar looks "busy")
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=180)

    # --------------------------------------------------------------------- helpers
    def set_status(self, message: str, tone: str = "info") -> None:
        self.status_label.configure(text=message, foreground=STATUS_TONES.get(tone, COLORS["text"]))

    def _on_busy(self, busy: bool) -> None:
        if busy:
            self.progress.pack(side="right")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def show_error(self, title: str, message: str) -> None:
        self.last_dialog = ("error", title, message)
        if self.quiet_dialogs:
            return
        messagebox.showerror(title, message, parent=self.root)

    def show_info(self, title: str, message: str) -> None:
        self.last_dialog = ("info", title, message)
        if self.quiet_dialogs:
            return
        messagebox.showinfo(title, message, parent=self.root)

    def select_tab(self, name: str) -> None:
        self.notebook.select(self.tabs[name])

    def _on_tab_changed(self, _event: tk.Event | None = None) -> None:
        try:
            current = self.notebook.nametowidget(self.notebook.select())
        except (KeyError, tk.TclError):
            return
        on_show = getattr(current, "on_show", None)
        if callable(on_show):
            on_show()

    def close(self) -> None:
        self.runner.shutdown()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def launch_app(argv: list[str] | None = None) -> int:
    """Create the Tk root, build ``CT204App`` and run the main loop.

    ``--smoke`` builds every tab, runs one idle cycle and exits (headless startup check).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    smoke = "--smoke" in args
    if not smoke:
        enable_windows_dpi_awareness()
    root = tk.Tk()
    if smoke:
        root.withdraw()
    app = CT204App(root, quiet_dialogs=smoke)
    if smoke:
        root.update_idletasks()
        root.update()
        for name in ("decrypt", "compare", "benchmark", "encrypt"):
            app.select_tab(name)
            root.update_idletasks()
        root.after(300, app.close)
    root.mainloop()
    return 0
