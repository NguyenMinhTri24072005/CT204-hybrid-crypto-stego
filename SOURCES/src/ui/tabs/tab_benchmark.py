"""Tab 4 — Dashboard 8.000 ảnh Linnaeus 5 & đối chiếu Bảng 2 bài báo (offline từ CSV)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

from src.ui import plots
from src.ui.controller import (
    CIPHER_LABELS,
    BenchmarkBundle,
    fmt_num,
    load_benchmark_bundle,
)
from src.ui.tabs.common import existing_dir
from src.ui.widgets import KpiBadgeRow, MatplotlibCard, ScrollableFrame, StyledTreeview

if TYPE_CHECKING:
    from src.ui.app_window import CT204App

ALL = "Tất cả"
CHART_PAPER = "Đối chiếu Bài báo vs Thực nghiệm (PSNR, NPCR, UACI, EncTime log)"
CHART_CLASSES = "Phân bố PSNR / SSIM / Entropy Stego theo 5 lớp ảnh"
CHART_TIME = "Phân bố thời gian mã hóa EncTime (µs) của 3 thuật toán"


class BenchmarkTab(ttk.Frame):
    def __init__(self, master: tk.Misc, app: CT204App) -> None:
        super().__init__(master, padding=(8, 8, 8, 4))
        self.app = app
        self.cfg = app.cfg
        self.bundle: BenchmarkBundle | None = None
        self._loading = False
        self._loaded_once = False
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self, style="Card.TFrame", padding=10)
        bar.pack(fill="x", pady=(0, 8))
        self.source_label = ttk.Label(bar, text="Chưa nạp dữ liệu benchmark.", style="Muted.TLabel")
        self.source_label.pack(side="left")
        ttk.Button(bar, text="📂 Nạp file CSV khác...", command=self.choose_csv).pack(side="right")
        self.reload_btn = ttk.Button(bar, text="🔄 Nạp lại results/", command=self.load_default)
        self.reload_btn.pack(side="right", padx=(0, 8))

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        body = self.scroll.inner

        self.kpis = KpiBadgeRow(body)
        self.kpis.pack(fill="x", pady=(0, 6))
        self.kpis.set_items([("Trạng thái", "Đang chờ nạp CSV...", "neutral")])

        card = ttk.Frame(body, style="Card.TFrame", padding=8)
        card.pack(fill="x", pady=(0, 8))
        ttk.Label(card, text="Python Reproduction vs. MATLAB Paper — Bảng 2 (Raut et al., ICITSC 2025)",
                  style="CardTitle.TLabel").pack(anchor="w")
        self.table = StyledTreeview(card, [
            ("metric", "Chỉ số", 150, "w"),
            ("3des_ours", "3DES (ours)", 105, "e"), ("3des_paper", "3DES (paper)", 105, "e"),
            ("3des_delta", "Δ 3DES", 90, "e"),
            ("aes_ours", "AES (ours)", 105, "e"), ("aes_paper", "AES (paper)", 105, "e"),
            ("aes_delta", "Δ AES", 90, "e"),
            ("chaotic_ours", "Chaotic (ours)", 105, "e"), ("chaotic_paper", "Chaotic (paper)", 105, "e"),
            ("chaotic_delta", "Δ Chaotic", 90, "e"),
        ], height=9, show_hscroll=True)
        self.table.pack(fill="x", pady=(4, 0))
        ttk.Label(card, text="Bảng 2 chỉ có 1 cột “Avg. Entropy” — dùng chung cho Entropy Stego và "
                  "Entropy Cipher (xem BM-08). Bảng ở trên tính theo bộ lọc hiện tại.",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

        filters = ttk.Frame(body, style="Card.TFrame", padding=8)
        filters.pack(fill="x", pady=(0, 8))
        ttk.Label(filters, text="Tập dữ liệu:").grid(row=0, column=0, sticky="w")
        self.split_var = tk.StringVar(value=ALL)
        self.split_combo = ttk.Combobox(filters, textvariable=self.split_var, state="readonly",
                                        width=10, values=[ALL, "train", "test"])
        self.split_combo.grid(row=0, column=1, padx=(6, 16))
        ttk.Label(filters, text="Lớp ảnh Linnaeus 5:").grid(row=0, column=2, sticky="w")
        self.class_var = tk.StringVar(value=ALL)
        self.class_combo = ttk.Combobox(filters, textvariable=self.class_var, state="readonly",
                                        width=10, values=[ALL, "berry", "bird", "dog", "flower", "other"])
        self.class_combo.grid(row=0, column=3, padx=(6, 16))
        ttk.Label(filters, text="Loại biểu đồ:").grid(row=0, column=4, sticky="w")
        self.chart_var = tk.StringVar(value=CHART_PAPER)
        self.chart_combo = ttk.Combobox(filters, textvariable=self.chart_var, state="readonly",
                                        width=58, values=[CHART_PAPER, CHART_CLASSES, CHART_TIME])
        self.chart_combo.grid(row=0, column=5, padx=(6, 0))
        self.filter_info = ttk.Label(filters, text="", style="Muted.TLabel")
        self.filter_info.grid(row=1, column=0, columnspan=6, sticky="w", pady=(6, 0))
        for combo in (self.split_combo, self.class_combo, self.chart_combo):
            combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        self.chart = MatplotlibCard(body, figsize=(11.5, 3.9), toolbar=True)
        self.chart.pack(fill="x")
        self.chart.show_message("Dữ liệu benchmark sẽ được nạp khi mở tab này.")

    # -------------------------------------------------------------------- loading
    def on_show(self) -> None:
        if not self._loaded_once and not self._loading:
            self.load_default()

    def load_default(self) -> None:
        self._load(results_dir=Path(self.cfg["paths"]["results_dir"]))

    def choose_csv(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="Chọn benchmark_summary_table2.csv (file chi tiết cùng thư mục sẽ tự nạp)",
            initialdir=existing_dir(self.cfg["paths"]["results_dir"]),
            filetypes=[("CSV", "*.csv")])
        if path:
            self._load(summary_path=Path(path))

    def _load(self, **kwargs) -> None:
        self._loading = True
        self.reload_btn.configure(state="disabled")
        self.app.set_status("Đang nạp CSV benchmark 8.000 ảnh (luồng nền)...")
        self.app.runner.submit(load_benchmark_bundle, **kwargs, on_success=self.show_bundle,
                               on_error=self._on_error)

    def _on_error(self, exc: BaseException, _tb: str) -> None:
        self._loading = False
        self._loaded_once = True
        self.reload_btn.configure(state="normal")
        self.kpis.set_items([("Trạng thái", "Không nạp được CSV", "bad")])
        self.chart.show_message(f"Không nạp được dữ liệu benchmark:\n{exc}")
        self.app.set_status(f"Lỗi nạp benchmark: {exc}", tone="bad")

    def show_bundle(self, bundle: BenchmarkBundle) -> None:
        self._loading = False
        self._loaded_once = True
        self.reload_btn.configure(state="normal")
        self.bundle = bundle
        ov = bundle.overview()
        details = "" if bundle.details_path is None else f" + {bundle.details_path.name}"
        self.source_label.configure(text=f"Nguồn: {bundle.summary_path}{details}")
        exact = ov["exact_rate"]
        self.kpis.set_items([
            ("Tổng số ảnh", f"{ov['n_images']:,}", "info"),
            ("Tổng lượt mã hóa–giải mã", f"{ov['n_runs']:,}", "info"),
            ("Khôi phục chính xác (MSE=0)", f"{exact:.2%}" if exact == exact else "—",
             "ok" if exact == 1.0 else "bad"),
            ("Cấu hình", ov["config"], "neutral"),
        ])
        has_details = bundle.details is not None
        for combo in (self.split_combo, self.class_combo):
            combo.configure(state="readonly" if has_details else "disabled")
        self.refresh()
        self.app.set_status(f"Đã nạp benchmark: {ov['n_runs']:,} lượt trên {ov['n_images']:,} ảnh.",
                            tone="ok")

    # ------------------------------------------------------------------ rendering
    def _filtered(self):
        bundle = self.bundle
        if bundle is None or bundle.details is None:
            return None
        split = self.split_var.get()
        cls = self.class_var.get()
        return bundle.filter_details(None if split == ALL else split, None if cls == ALL else cls)

    def refresh(self) -> None:
        bundle = self.bundle
        if bundle is None:
            return
        details = self._filtered()
        if details is not None:
            self.filter_info.configure(
                text=f"{len(details):,} lượt sau lọc ({details['image_index'].nunique():,} ảnh)")
        else:
            self.filter_info.configure(text="Chỉ có file tổng hợp — bộ lọc và biểu đồ phân bố bị tắt.")
        comp = bundle.comparison_table(details if details is not None and not details.empty else None)
        rows = []
        for key, group in comp.groupby("metric", sort=False):
            label = group["label"].iloc[0]
            row = [label]
            for name in ("3des", "aes", "chaotic"):
                g = group[group["cipher"] == name]
                if g.empty:
                    row += ["—", "—", "—"]
                    continue
                digits = 6 if key in ("ssim", "corr_enc") else 4
                row += [fmt_num(g["ours"].iloc[0], digits), fmt_num(g["paper"].iloc[0], digits),
                        fmt_num(g["delta"].iloc[0], digits)]
            rows.append(row)
        self.table.set_rows(rows)

        chart = self.chart_var.get()
        if chart == CHART_PAPER:
            ours = bundle.ours(details if details is not None and not details.empty else None)
            self.chart.draw(lambda fig: plots.draw_paper_vs_ours(fig, ours, bundle.paper_reference))
        elif details is None:
            self.chart.show_message("Biểu đồ phân bố cần file benchmark_results.csv (chi tiết từng ảnh).")
        elif chart == CHART_CLASSES:
            self.chart.draw(lambda fig: plots.draw_class_distributions(fig, details))
        else:
            self.chart.draw(lambda fig: plots.draw_enctime_distribution(fig, details))

    @staticmethod
    def cipher_label(name: str) -> str:
        return CIPHER_LABELS.get(name, name)
