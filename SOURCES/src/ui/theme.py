"""Bright, high-contrast academic theme (readable on projectors) built on ``ttk`` 'clam'."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

COLORS = {
    "bg": "#F4F6F9",  # main background
    "card": "#FFFFFF",  # card background
    "border": "#D8E0EA",  # thin borders
    "navy": "#1E3A5F",  # primary accent
    "blue": "#2563EB",  # secondary accent / primary buttons
    "blue_dark": "#1D4ED8",
    "ok": "#15803D",  # integrity OK (MSE == 0, CRC OK)
    "bad": "#B91C1C",  # attack / error (CRC mismatch, wrong key)
    "warn": "#B45309",
    "text": "#1F2937",
    "muted": "#5B6B7F",
    "ok_bg": "#DCFCE7",
    "bad_bg": "#FEE2E2",
    "info_bg": "#E0ECFF",
    "warn_bg": "#FEF3C7",
    "stripe": "#F1F5FB",
    "header_sub": "#C7D6EA",
}

# One colour per cipher, reused by every chart.
CIPHER_COLORS = {"3des": "#1E3A5F", "aes": "#2563EB", "chaotic": "#15803D"}
PAPER_COLOR = "#9CA3AF"
HIST_COLOR = "#1F3B4D"

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"
FONTS = {
    "body": (FONT_FAMILY, 10),
    "bold": (FONT_FAMILY, 10, "bold"),
    "small": (FONT_FAMILY, 9),
    "card_title": (FONT_FAMILY, 10, "bold"),
    "title": (FONT_FAMILY, 15, "bold"),
    "subtitle": (FONT_FAMILY, 10),
    "mono": (MONO_FAMILY, 10),
    "mono_bold": (MONO_FAMILY, 10, "bold"),
    "kpi_label": (FONT_FAMILY, 9),
    "kpi_value": (FONT_FAMILY, 12, "bold"),
    "banner": (FONT_FAMILY, 11, "bold"),
}

TONE_COLORS = {
    "ok": (COLORS["ok_bg"], COLORS["ok"]),
    "bad": (COLORS["bad_bg"], COLORS["bad"]),
    "warn": (COLORS["warn_bg"], COLORS["warn"]),
    "info": (COLORS["info_bg"], COLORS["navy"]),
    "neutral": (COLORS["card"], COLORS["text"]),
}


def enable_windows_dpi_awareness() -> bool:
    """Make Tk render crisply on high-DPI Windows screens. Must run before ``tk.Tk()``.

    Returns True when a DPI-awareness call succeeded; never raises.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # system-DPI aware
            return True
        except (AttributeError, OSError):
            return bool(ctypes.windll.user32.SetProcessDPIAware())
    except Exception:  # noqa: BLE001 - purely cosmetic, must never break startup
        return False


def apply_theme(root: tk.Misc) -> ttk.Style:
    """Configure ttk styles and default fonts; returns the ``ttk.Style``."""
    style = ttk.Style(root)
    style.theme_use("clam")
    c = COLORS

    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(family=FONT_FAMILY, size=10)
        except tk.TclError:
            pass
    root.option_add("*TCombobox*Listbox.font", FONTS["body"])
    if isinstance(root, (tk.Tk, tk.Toplevel)):
        root.configure(background=c["bg"])

    style.configure(".", background=c["bg"], foreground=c["text"], font=FONTS["body"],
                    bordercolor=c["border"], focuscolor=c["blue"])
    style.configure("TFrame", background=c["bg"])
    style.configure("Card.TFrame", background=c["card"], bordercolor=c["border"],
                    lightcolor=c["card"], darkcolor=c["card"], relief="solid", borderwidth=1)
    style.configure("Plain.TFrame", background=c["card"])

    style.configure("TLabel", background=c["card"], foreground=c["text"])
    style.configure("Bg.TLabel", background=c["bg"])
    style.configure("CardTitle.TLabel", background=c["card"], foreground=c["navy"],
                    font=FONTS["card_title"])
    style.configure("Section.TLabel", background=c["bg"], foreground=c["navy"],
                    font=(FONT_FAMILY, 11, "bold"))
    style.configure("Muted.TLabel", background=c["card"], foreground=c["muted"], font=FONTS["small"])
    style.configure("Mono.TLabel", background=c["card"], font=FONTS["mono"])
    style.configure("MonoBold.TLabel", background=c["card"], font=FONTS["mono_bold"])
    style.configure("Ok.TLabel", background=c["card"], foreground=c["ok"], font=FONTS["mono_bold"])
    style.configure("Bad.TLabel", background=c["card"], foreground=c["bad"], font=FONTS["mono_bold"])
    style.configure("Status.TLabel", background=c["card"], foreground=c["text"])

    style.configure("TLabelframe", background=c["card"], bordercolor=c["border"],
                    lightcolor=c["card"], darkcolor=c["card"], relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=c["card"], foreground=c["navy"],
                    font=FONTS["card_title"])

    style.configure("TCheckbutton", background=c["card"])
    style.map("TCheckbutton", background=[("active", c["card"])])
    style.configure("TRadiobutton", background=c["card"])
    style.map("TRadiobutton", background=[("active", c["card"])])

    style.configure("TButton", padding=(10, 5), background="#EEF2F7", bordercolor=c["border"],
                    lightcolor="#F8FAFC", darkcolor="#E2E8F0")
    style.map("TButton", background=[("disabled", "#F1F5F9"), ("active", "#E2E8F0")],
              foreground=[("disabled", "#9CA3AF")])
    style.configure("Primary.TButton", padding=(12, 7), background=c["blue"], foreground="white",
                    bordercolor=c["blue_dark"], lightcolor=c["blue"], darkcolor=c["blue_dark"],
                    font=FONTS["bold"])
    style.map("Primary.TButton",
              background=[("disabled", "#93B4F5"), ("active", c["blue_dark"])],
              foreground=[("disabled", "#EEF2FF")])
    style.configure("Danger.TButton", foreground=c["bad"])

    style.configure("TEntry", fieldbackground="white", bordercolor=c["border"])
    style.configure("TCombobox", fieldbackground="white", bordercolor=c["border"])
    style.map("TCombobox", fieldbackground=[("readonly", "white")])
    style.configure("TSpinbox", fieldbackground="white", bordercolor=c["border"])

    style.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=(8, 6, 8, 0))
    style.configure("TNotebook.Tab", padding=(16, 7), background="#E5EAF1", foreground=c["muted"],
                    font=FONTS["bold"], bordercolor=c["border"])
    style.map("TNotebook.Tab", background=[("selected", c["card"])],
              foreground=[("selected", c["navy"])])

    style.configure("Treeview", background="white", fieldbackground="white", rowheight=24,
                    font=FONTS["body"], bordercolor=c["border"])
    style.configure("Treeview.Heading", background=c["navy"], foreground="white",
                    font=FONTS["bold"], relief="flat", padding=(6, 4))
    style.map("Treeview.Heading", background=[("active", c["blue"])])
    style.map("Treeview", background=[("selected", "#CFE0FF")],
              foreground=[("selected", c["text"])])

    style.configure("Horizontal.TProgressbar", background=c["blue"], troughcolor="#E5EAF1",
                    bordercolor=c["border"], lightcolor=c["blue"], darkcolor=c["blue"])
    style.configure("TScrollbar", background="#E2E8F0", troughcolor=c["bg"],
                    bordercolor=c["border"], arrowcolor=c["muted"])
    return style
