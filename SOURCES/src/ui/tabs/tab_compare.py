"""Tab 3 — So sánh trực tiếp 3 thuật toán & tái hiện Hình 4–5 (Live Comparison)."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

from src.ui import plots
from src.ui.controller import (
    COMPARE_COLUMNS,
    KEY_MODE_PAPER,
    MATLAB_COINS_SHAPE,
    TABLE2_SECRET_SIZE,
    CompareWorkflowResult,
    export_compare_bundle,
    fmt_num,
    load_sample_cover,
    load_sample_secret,
    run_compare_workflow,
)
from src.ui.resources import get_default_export_dir
from src.ui.tabs.common import existing_dir
from src.ui.widgets import MatplotlibCard, ScrollableFrame, StyledTreeview

if TYPE_CHECKING:
    from src.ui.app_window import CT204App

SOURCE_TAB1 = "tab1"
SOURCE_SAMPLE = "sample"
PRESET_FIG5 = "246×300 — Hình 5 (giữ nguyên gốc)"
PRESET_TABLE2 = "156×156 — Bảng 2 (1-LSB)"

_COL_WIDTHS = {"Thuật toán": 170, "Cover Used": 110, "Tăng tốc so với 3DES (×)": 150,
               "Khôi phục (MSE=0)": 120}


class CompareTab(ttk.Frame):
    def __init__(self, master: tk.Misc, app: CT204App) -> None:
        super().__init__(master, padding=(8, 8, 8, 4))
        self.app = app
        self.cfg = app.cfg
        self.result: CompareWorkflowResult | None = None
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self, style="Card.TFrame", padding=10)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Nguồn:").grid(row=0, column=0, sticky="w")
        self.source_var = tk.StringVar(value=SOURCE_SAMPLE)
        ttk.Radiobutton(bar, text="Cặp mẫu (cover.jpg + coins)", value=SOURCE_SAMPLE,
                        variable=self.source_var).grid(row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Radiobutton(bar, text="Cặp đang chọn ở Tab 1", value=SOURCE_TAB1,
                        variable=self.source_var).grid(row=0, column=2, sticky="w", padx=(6, 0))
        ttk.Label(bar, text="Kích thước Secret:").grid(row=0, column=3, sticky="w", padx=(18, 0))
        self.preset_var = tk.StringVar(value=PRESET_FIG5)
        ttk.Combobox(bar, textvariable=self.preset_var, state="readonly", width=30,
                     values=[PRESET_FIG5, PRESET_TABLE2]).grid(row=0, column=4, sticky="w", padx=(6, 0))
        self.cache_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Pre-cache Chaotic Mask (BM-10)", variable=self.cache_var).grid(
            row=1, column=1, columnspan=2, sticky="w", pady=(6, 0), padx=(6, 0))
        ttk.Label(bar, text="Khóa: Chuẩn bài báo (Seed 2025)", style="Muted.TLabel").grid(
            row=1, column=3, columnspan=2, sticky="w", padx=(18, 0), pady=(6, 0))
        self.run_btn = ttk.Button(bar, text="⚡ Chạy So sánh cả 3 Thuật toán",
                                  style="Primary.TButton", command=self.run)
        self.run_btn.grid(row=0, column=5, rowspan=2, padx=(18, 0), sticky="ns")
        self.export_btn = ttk.Button(bar, text="📤 Xuất bộ ảnh Hình 4, Hình 5 & CSV...",
                                     command=self.export, state="disabled")
        self.export_btn.grid(row=0, column=6, rowspan=2, padx=(8, 0), sticky="ns")

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        body = self.scroll.inner

        card = ttk.Frame(body, style="Card.TFrame", padding=8)
        card.pack(fill="x", pady=(0, 8))
        ttk.Label(card, text="Bảng so sánh ngang 3DES · AES · Chaotic", style="CardTitle.TLabel").pack(
            anchor="w")
        self.table = StyledTreeview(
            card, [(c, c, _COL_WIDTHS.get(c, 92), "w" if c == "Thuật toán" else "e")
                   for c in COMPARE_COLUMNS], height=3, show_hscroll=True)
        self.table.pack(fill="x", pady=(4, 0))

        mode_row = ttk.Frame(body)
        mode_row.pack(fill="x", pady=(0, 4))
        ttk.Label(mode_row, text="Chế độ xem:", style="Bg.TLabel").pack(side="left")
        self.view_var = tk.StringVar(value="fig5")
        for value, text in (("fig5", "A — Tái hiện Hình 5 (lưới 3×3)"),
                            ("speed", "B — Tốc độ mã hóa & Ảnh khôi phục")):
            rb = tk.Radiobutton(mode_row, text=text, value=value, variable=self.view_var,
                                command=self.redraw, background=self.app.colors["bg"],
                                activebackground=self.app.colors["bg"], font=("Segoe UI", 10))
            rb.pack(side="left", padx=(10, 0))
        self.chart = MatplotlibCard(body, figsize=(11.5, 8.2))
        self.chart.pack(fill="x")
        self.chart.show_message("Bấm “⚡ Chạy So sánh cả 3 Thuật toán” để tái hiện Hình 5 bài báo.")

    # ------------------------------------------------------------------ actions
    def _inputs(self):
        if self.source_var.get() == SOURCE_TAB1:
            tab = self.app.tab_encrypt
            if tab.cover_rgb is None or tab.secret_gray is None:
                raise ValueError("Tab 1 chưa có đủ ảnh Cover và Secret.")
            return tab.cover_rgb, tab.secret_gray
        return load_sample_cover(self.cfg), load_sample_secret(self.cfg)

    def run(self) -> None:
        try:
            cover, secret = self._inputs()
        except (OSError, ValueError) as exc:
            self.app.show_error("Thiếu ảnh đầu vào", str(exc))
            return
        size = TABLE2_SECRET_SIZE if self.preset_var.get() == PRESET_TABLE2 else (
            MATLAB_COINS_SHAPE if self.source_var.get() == SOURCE_SAMPLE else None)
        self.run_btn.configure(state="disabled")
        self.app.set_status("Đang chạy 3DES → AES → Chaotic trên cùng cặp ảnh...")
        self.app.runner.submit(run_compare_workflow, cover, secret, self.cfg,
                               key_mode=KEY_MODE_PAPER, cache_chaotic_mask=bool(self.cache_var.get()),
                               secret_size=size, on_success=self.show_result, on_error=self._on_error)

    def _on_error(self, exc: BaseException, _tb: str) -> None:
        self.run_btn.configure(state="normal")
        self.app.set_status(f"Lỗi khi so sánh: {exc}", tone="bad")
        self.app.show_error("So sánh thất bại", str(exc))

    def show_result(self, res: CompareWorkflowResult) -> None:
        self.result = res
        self.run_btn.configure(state="normal")
        self.export_btn.configure(state="normal")
        rows, tags = [], []
        for _, row in res.table.iterrows():
            values = []
            for col in COMPARE_COLUMNS:
                v = row[col]
                if col in ("Thuật toán", "Cover Used", "Khôi phục (MSE=0)", "num_lsb"):
                    values.append(v)
                elif col == "EncTime (µs)":
                    values.append(f"{v:,.1f}")
                elif col == "Tăng tốc so với 3DES (×)":
                    values.append(f"×{v:,.1f}")
                else:
                    values.append(fmt_num(v, 5 if col in ("SSIM", "Corr_enc") else 4))
            rows.append(values)
            tags.append(["ok"] if row["Khôi phục (MSE=0)"] == "✅" else ["bad"])
        self.table.set_rows(rows, tags)
        self.redraw()
        exact = all(r.is_exact for r in res.results.values())
        self.app.set_status(
            "So sánh xong 3 thuật toán — " + ("cả 3 khôi phục MSE = 0 ✅" if exact else "CÓ LỖI khôi phục ❌"),
            tone="ok" if exact else "bad")

    def redraw(self) -> None:
        res = self.result
        if res is None:
            return
        if self.view_var.get() == "speed":
            self.chart.draw(lambda fig: plots.draw_speed_and_recovered(fig, res.enc_times(), res.recovered()))
        else:
            self.chart.draw(lambda fig: plots.draw_figure5(fig, res.panels()))

    def export(self) -> None:
        if self.result is None:
            return
        folder = filedialog.askdirectory(parent=self, title="Chọn thư mục xuất Hình 4, Hình 5 & CSV",
                                         initialdir=existing_dir(get_default_export_dir()),
                                         mustexist=False)
        if not folder:
            return
        self.export_btn.configure(state="disabled")
        self.app.set_status(f"Đang xuất bộ ảnh vào {folder}...")
        self.app.runner.submit(export_compare_bundle, self.result, folder,
                               on_success=self._exported, on_error=self._export_failed)

    def _exported(self, paths) -> None:
        self.export_btn.configure(state="normal")
        folder = paths[0].parent if paths else ""
        self.app.set_status(f"Đã xuất {len(paths)} file vào {folder}", tone="ok")

    def _export_failed(self, exc: BaseException, _tb: str) -> None:
        self.export_btn.configure(state="normal")
        self.app.set_status(f"Xuất thất bại: {exc}", tone="bad")
        self.app.show_error("Xuất thất bại", str(exc))
