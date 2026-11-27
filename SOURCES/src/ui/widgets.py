"""Reusable Tk widgets: scrollable frame, image cards, KPI badges, tables, matplotlib cards.

Matplotlib is used strictly object-oriented (``matplotlib.figure.Figure`` +
``FigureCanvasTkAgg``); ``matplotlib.pyplot`` is never imported in ``src/ui``.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import ttk
from typing import Any

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from PIL import Image, ImageTk

from src.ui.theme import COLORS, FONTS, TONE_COLORS


# --------------------------------------------------------------------------- helpers
def array_to_pil(img: np.ndarray) -> Image.Image:
    """uint8 (H, W) gray or (H, W, 3) RGB array -> PIL image."""
    arr = np.ascontiguousarray(img)
    if arr.dtype != np.uint8:
        raise ValueError(f"image must be uint8, got {arr.dtype}")
    if arr.ndim == 2:
        return Image.fromarray(arr, mode="L")
    if arr.ndim == 3 and arr.shape[2] == 3:
        return Image.fromarray(arr, mode="RGB")
    raise ValueError(f"unsupported image shape {arr.shape}")


def fit_size(w: int, h: int, max_w: int, max_h: int, *, allow_upscale: bool = True) -> tuple[int, int]:
    """Largest size with the same aspect ratio that fits in ``max_w × max_h``."""
    scale = min(max_w / w, max_h / h)
    if not allow_upscale:
        scale = min(scale, 1.0)
    return max(1, int(round(w * scale))), max(1, int(round(h * scale)))


def resize_for_display(pil: Image.Image, max_w: int, max_h: int, *, max_upscale: float = 4.0) -> Image.Image:
    """Keep aspect ratio; NEAREST when enlarging (shows pixels/noise), LANCZOS when shrinking."""
    w, h = pil.size
    scale = min(max_w / w, max_h / h, max_upscale)
    size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    if size == (w, h):
        return pil
    resample = Image.Resampling.NEAREST if scale >= 1.0 else Image.Resampling.LANCZOS
    return pil.resize(size, resample)


# ------------------------------------------------------------------- ScrollableFrame
class ScrollableFrame(ttk.Frame):
    """Vertical scroll container (Canvas + ttk.Scrollbar) with mouse-wheel support.

    Put children in ``.inner``. The wheel scrolls the ScrollableFrame under the pointer
    (one global ``<MouseWheel>`` binding per Tk root), except over widgets that scroll
    themselves (Treeview, Listbox, Text).
    """

    def __init__(self, master: tk.Misc, *, width: int | None = None, inner_style: str = "TFrame",
                 fit_width: bool = False, **kwargs: Any) -> None:
        """``fit_width=True``: the canvas always matches the content's requested width
        (used for the left control column so nothing is clipped at high DPI scaling)."""
        super().__init__(master, **kwargs)
        self.fit_width = fit_width
        self.canvas = tk.Canvas(self, background=COLORS["bg"], highlightthickness=0, borderwidth=0)
        if width is not None:
            self.canvas.configure(width=width)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.inner = ttk.Frame(self.canvas, style=inner_style)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._install_wheel_handler()

    def _on_inner_configure(self, _event: tk.Event) -> None:
        if self.fit_width:
            req = self.inner.winfo_reqwidth()
            if int(self.canvas.cget("width")) != req:
                self.canvas.configure(width=req)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        req = self.inner.winfo_reqwidth()
        self.canvas.itemconfigure(self._window, width=max(event.width, req))

    def can_scroll(self) -> bool:
        return self.inner.winfo_reqheight() > self.canvas.winfo_height()

    def scroll_units(self, units: int) -> None:
        if units and self.can_scroll():
            self.canvas.yview_scroll(units, "units")

    def scroll_to_top(self) -> None:
        self.canvas.yview_moveto(0.0)

    # global wheel dispatch ----------------------------------------------------------
    _WHEEL_FLAG = "ct204_wheel_installed"

    def _install_wheel_handler(self) -> None:
        # bind_all is interpreter-wide, so install exactly once per Tcl interpreter
        # (several windows/Toplevels must not stack duplicate handlers).
        if self.tk.getboolean(self.tk.call("info", "exists", self._WHEEL_FLAG)):
            return
        self.setvar(self._WHEEL_FLAG, 1)
        self.bind_all("<MouseWheel>", ScrollableFrame._dispatch_wheel, add="+")
        self.bind_all("<Button-4>", ScrollableFrame._dispatch_wheel, add="+")  # X11
        self.bind_all("<Button-5>", ScrollableFrame._dispatch_wheel, add="+")

    @staticmethod
    def _dispatch_wheel(event: tk.Event) -> str | None:
        try:
            widget = event.widget.winfo_containing(event.x_root, event.y_root)
        except (tk.TclError, KeyError, AttributeError):
            return None
        while widget is not None:
            if isinstance(widget, (ttk.Treeview, tk.Listbox, tk.Text)):
                return None  # let self-scrolling widgets handle it
            if isinstance(widget, ScrollableFrame):
                if getattr(event, "num", None) == 4:
                    units = -1
                elif getattr(event, "num", None) == 5:
                    units = 1
                else:
                    delta = int(getattr(event, "delta", 0))
                    units = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
                if widget.can_scroll():
                    widget.scroll_units(units)
                    return "break"
            widget = getattr(widget, "master", None)
        return None


# -------------------------------------------------------------------- ImagePreviewCard
class ImagePreviewCard(ttk.Frame):
    """Card with a title, an aspect-preserving image and a caption.

    Double-click the image to open an enlarged view in a ``Toplevel`` window.
    ``.footer`` is a free frame under the caption for extra controls.
    """

    def __init__(self, master: tk.Misc, title: str, *, box: tuple[int, int] = (240, 200),
                 placeholder: str = "(chưa có ảnh)") -> None:
        super().__init__(master, style="Card.TFrame", padding=8)
        self.box = box
        self.placeholder = placeholder
        self._array: np.ndarray | None = None
        self._photo: ImageTk.PhotoImage | None = None
        self._zoom_windows: list[tk.Toplevel] = []

        self.title_label = ttk.Label(self, text=title, style="CardTitle.TLabel")
        self.title_label.pack(anchor="w")
        self.image_label = tk.Label(self, background="#EEF2F7", foreground=COLORS["muted"],
                                    width=box[0], height=box[1], text=placeholder,
                                    font=FONTS["small"], cursor="hand2", compound="center")
        # width/height of a tk.Label with an image are in pixels; keep a fixed box
        self.image_label.configure(width=box[0], height=box[1])
        self._blank = tk.PhotoImage(master=self, width=box[0], height=box[1])
        self.image_label.configure(image=self._blank)
        self.image_label.pack(pady=(6, 4))
        self.caption = ttk.Label(self, text="", style="Muted.TLabel", wraplength=box[0],
                                 justify="center")
        self.caption.pack()
        self.footer = ttk.Frame(self, style="Plain.TFrame")
        self.footer.pack(fill="x")
        self.image_label.bind("<Double-Button-1>", lambda _e: self.open_zoom())

    @property
    def array(self) -> np.ndarray | None:
        return self._array

    def set_title(self, title: str) -> None:
        self.title_label.configure(text=title)

    def set_caption(self, text: str, *, tone: str | None = None) -> None:
        style = {"ok": "Ok.TLabel", "bad": "Bad.TLabel"}.get(tone or "", "Muted.TLabel")
        self.caption.configure(text=text, style=style)

    def set_image(self, img: np.ndarray | None, caption: str | None = None, *,
                  tone: str | None = None) -> None:
        """Show ``img`` (uint8 gray/RGB) or the placeholder when ``None``. Main thread only."""
        self._array = None if img is None else np.asarray(img)
        if img is None:
            self._photo = None
            self.image_label.configure(image=self._blank, text=self.placeholder)
        else:
            pil = resize_for_display(array_to_pil(self._array), *self.box)
            self._photo = ImageTk.PhotoImage(pil, master=self)
            self.image_label.configure(image=self._photo, text="")
        if caption is not None:
            self.set_caption(caption, tone=tone)

    def open_zoom(self) -> tk.Toplevel | None:
        if self._array is None:
            return None
        top = tk.Toplevel(self)
        top.title(f"Phóng lớn — {self.title_label.cget('text')}")
        top.configure(background=COLORS["bg"])
        sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
        pil = resize_for_display(array_to_pil(self._array), int(sw * 0.8), int(sh * 0.75),
                                 max_upscale=6.0)
        photo = ImageTk.PhotoImage(pil, master=top)
        label = tk.Label(top, image=photo, background=COLORS["bg"])
        label.image = photo  # keep a reference
        label.pack(padx=12, pady=(12, 4))
        h, w = self._array.shape[:2]
        ttk.Label(top, text=f"{w}×{h} px — hiển thị {pil.size[0]}×{pil.size[1]} (NEAREST khi phóng)",
                  style="Bg.TLabel").pack(pady=(0, 10))
        top.bind("<Escape>", lambda _e: top.destroy())
        top.focus_set()
        self._zoom_windows.append(top)
        return top


# ------------------------------------------------------------------------ KPI badges
class KpiBadgeRow(ttk.Frame):
    """Row of small KPI badges: ``set_items([(label, value, tone), ...])``."""

    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self._badges: list[tk.Frame] = []

    def set_items(self, items: Sequence[tuple[str, str, str]]) -> None:
        for badge in self._badges:
            badge.destroy()
        self._badges = []
        for i, (label, value, tone) in enumerate(items):
            bg, fg = TONE_COLORS.get(tone, TONE_COLORS["neutral"])
            badge = tk.Frame(self, background=bg, highlightbackground=COLORS["border"],
                             highlightthickness=1, padx=10, pady=5)
            tk.Label(badge, text=label, background=bg, foreground=COLORS["muted"],
                     font=FONTS["kpi_label"]).pack(anchor="w")
            tk.Label(badge, text=value, background=bg, foreground=fg,
                     font=FONTS["kpi_value"]).pack(anchor="w")
            badge.grid(row=i // 4 if len(items) > 8 else 0, column=i % 4 if len(items) > 8 else i,
                       padx=(0, 8), pady=4, sticky="nsew")
            self._badges.append(badge)

    def values(self) -> list[str]:
        out = []
        for badge in self._badges:
            labels = badge.winfo_children()
            out.append(labels[1].cget("text"))
        return out


# --------------------------------------------------------------------- StyledTreeview
class StyledTreeview(ttk.Frame):
    """Treeview with zebra striping and ok/bad row tags.

    ``columns`` is a sequence of ``(id, heading, width, anchor)``.
    """

    def __init__(self, master: tk.Misc, columns: Sequence[tuple[str, str, int, str]], *,
                 height: int = 4, show_hscroll: bool = False) -> None:
        super().__init__(master, style="Plain.TFrame")
        self.column_ids = [c[0] for c in columns]
        self.tree = ttk.Treeview(self, columns=self.column_ids, show="headings", height=height,
                                 selectmode="browse")
        for cid, heading, width, anchor in columns:
            self.tree.heading(cid, text=heading, anchor=anchor)
            self.tree.column(cid, width=width, minwidth=40, anchor=anchor, stretch=True)
        self.tree.tag_configure("even", background="white")
        self.tree.tag_configure("odd", background=COLORS["stripe"])
        self.tree.tag_configure("ok", foreground=COLORS["ok"])
        self.tree.tag_configure("bad", foreground=COLORS["bad"])
        self.tree.tag_configure("group", font=FONTS["bold"], foreground=COLORS["navy"])
        self.tree.grid(row=0, column=0, sticky="nsew")
        if show_hscroll:
            hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
            self.tree.configure(xscrollcommand=hsb.set)
            hsb.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def set_rows(self, rows: Sequence[Sequence[Any]], tags: Sequence[Sequence[str]] | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(rows):
            row_tags = ["odd" if i % 2 else "even"]
            if tags is not None and i < len(tags):
                row_tags.extend(tags[i])
            self.tree.insert("", "end", values=list(row), tags=row_tags)

    def rows(self) -> list[list[Any]]:
        return [list(self.tree.item(i, "values")) for i in self.tree.get_children()]


# ---------------------------------------------------------------------- MatplotlibCard
class MatplotlibCard(ttk.Frame):
    """Embeds an OOP ``Figure`` through ``FigureCanvasTkAgg``. Redraw with ``draw(fn)``."""

    def __init__(self, master: tk.Misc, *, figsize: tuple[float, float] = (8.0, 3.0),
                 title: str | None = None, toolbar: bool = False) -> None:
        super().__init__(master, style="Card.TFrame", padding=6)
        if title:
            ttk.Label(self, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 4))
        self.figure = Figure(figsize=figsize, dpi=100, facecolor="white")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.toolbar: NavigationToolbar2Tk | None = None
        if toolbar:
            self.toolbar = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
            self.toolbar.update()
            self.toolbar.pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def draw(self, painter: Callable[[Figure], None]) -> None:
        """Clear the figure, let ``painter(fig)`` draw, then ``draw_idle``. Main thread only."""
        self.figure.clear()
        painter(self.figure)
        self.canvas.draw_idle()

    def show_message(self, text: str) -> None:
        def paint(fig: Figure) -> None:
            ax = fig.add_subplot(111)
            ax.axis("off")
            ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=11, color=COLORS["muted"],
                    wrap=True)

        self.draw(paint)


# --------------------------------------------------------------------------- Banner
class Banner(tk.Label):
    """Coloured conclusion banner (tone: ok / bad / warn / info / neutral)."""

    def __init__(self, master: tk.Misc, text: str = "", tone: str = "info") -> None:
        super().__init__(master, text=text, font=FONTS["banner"], anchor="w", justify="left",
                         padx=14, pady=10, wraplength=760)
        self.set(text, tone)

    def set(self, text: str, tone: str = "info") -> None:
        bg, fg = TONE_COLORS.get(tone, TONE_COLORS["info"])
        self.configure(text=text, background=bg, foreground=fg)
        self.tone = tone
