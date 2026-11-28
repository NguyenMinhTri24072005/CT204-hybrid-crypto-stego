r"""Chụp màn hình 4 tab của ứng dụng cho báo cáo.

Cách chạy (từ SOURCES): .venv\Scripts\python.exe <đường dẫn>/shoot_ui.py <SOURCES> <thư mục ảnh ra>
"""
import sys
import time
from pathlib import Path

SOURCES = Path(sys.argv[1])
OUT = Path(sys.argv[2])
sys.path.insert(0, str(SOURCES))

from PIL import ImageGrab  # noqa: E402

from src.ui.app_window import CT204App  # noqa: E402
from src.ui.theme import enable_windows_dpi_awareness  # noqa: E402
import tkinter as tk  # noqa: E402

enable_windows_dpi_awareness()
root = tk.Tk()
app = CT204App(root, quiet_dialogs=True)
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
root.geometry(f"{min(1600, sw - 20)}x{min(900, sh - 60)}+0+0")


def pump(sec=0.5):
    end = time.time() + sec
    while time.time() < end or app.runner.busy:
        root.update()
        time.sleep(0.02)


def shot(name):
    pump(0.8)
    root.lift()
    root.attributes("-topmost", True)
    pump(0.4)
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(OUT / f"{name}.png")
    root.attributes("-topmost", False)


pump(1)
enc = app.tab_encrypt
enc.run()
pump()
enc.run()  # lần 2: EncTime không còn chi phí khởi động
pump()
shot("tab1_encrypt")
enc.send_to_decrypt()
pump()
app.tab_decrypt.try_wrong_key()
pump()
shot("tab2_wrongkey")
app.tab_decrypt.apply_tamper("flip_header_bit")
pump()
shot("tab2_tamper")
app.select_tab("compare")
app.tab_compare.run()
pump()
shot("tab3_compare")
app.select_tab("benchmark")
pump(2)
shot("tab4_benchmark")
app.close()
