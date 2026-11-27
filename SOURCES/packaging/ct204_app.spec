# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# SPECPATH là thư mục SOURCES/packaging -> parent là SOURCES/
ROOT = Path(SPECPATH).resolve().parent

# 1. Chọn đúng tài nguyên cần nhúng (không nhúng 8.000 ảnh gốc Linnaeus 5)
datas = [
    (str(ROOT / "configs" / "default.yaml"), "configs"),
    (str(ROOT / "data" / "sample" / "cover.jpg"), "data/sample"),
]

optional_files = [
    (ROOT / "data" / "sample" / "secret.png", "data/sample"),
    (ROOT / "results" / "benchmark_summary_table2.csv", "results"),
    (ROOT / "results" / "benchmark_results.csv", "results"),
]
for src_path, dest_dir in optional_files:
    if src_path.is_file():
        datas.append((str(src_path), dest_dir))

single_dir = ROOT / "results" / "single"
if single_dir.is_dir():
    for f in single_dir.iterdir():
        if f.suffix.lower() in {".png", ".csv"}:
            datas.append((str(f), "results/single"))

datas += collect_data_files("skimage", includes=["data/*"])

# 2. Thu thập các module động của PyCryptodome & Numba
hiddenimports = (
    collect_submodules("Crypto")
    + collect_submodules("numba")
    + collect_submodules("llvmlite")
)

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "_pytest", "IPython", "jupyter", "notebook"],
    noarchive=False,
    # Giữ kèm file .py cho package src để @numba.njit(cache=True) hoạt động mượt
    module_collection_mode={"src": "pyz+py"},
)

pyz = PYZ(a.pure)

# 3. Cấu hình chế độ THƯ MỤC ĐỘC LẬP (onedir): exclude_binaries=True + COLLECT
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CT204_CryptoStego",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Ẩn cửa sổ dòng lệnh đen phía sau giao diện
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CT204_CryptoStego",
)