"""Resource path resolution that works both from source and from a PyInstaller bundle.

Every UI access to ``configs/``, ``data/sample/`` and ``results/`` goes through this module
so that the same code runs unchanged in development and inside a frozen ``.exe``
(``sys.frozen`` + ``sys._MEIPASS``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

# src/ui/resources.py -> parents[2] == SOURCES/
_SOURCES_ROOT = Path(__file__).resolve().parents[2]
CONFIG_RELATIVE = Path("configs") / "default.yaml"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def get_resource_root() -> Path:
    """``Path(sys._MEIPASS)`` inside a PyInstaller bundle, otherwise the ``SOURCES/`` folder."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return _SOURCES_ROOT


def resource_path(*parts: str | Path) -> Path:
    """Absolute path of a bundled resource, e.g. ``resource_path("data", "sample")``."""
    return get_resource_root().joinpath(*parts)


def get_default_export_dir() -> Path:
    """Suggested folder for user exports (never created until the user saves something).

    Frozen: ``<folder of the .exe>/exports``; development: ``SOURCES/results/ui_exports``.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent / "exports"
    return get_resource_root() / "results" / "ui_exports"


def load_ui_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Read ``configs/default.yaml`` and resolve ``paths.*`` and ``secret.path`` against
    :func:`get_resource_root` so dev and ``.exe`` runs behave identically."""
    root = get_resource_root()
    path = Path(config_path) if config_path is not None else root / CONFIG_RELATIVE
    if not path.is_file():
        raise FileNotFoundError(f"không tìm thấy file cấu hình: {path}")
    with open(path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f) or {}

    for key, value in cfg.get("paths", {}).items():
        cfg["paths"][key] = _resolve(value, root)
    secret = cfg.get("secret")
    if secret and secret.get("path"):
        secret["path"] = _resolve(secret["path"], root)
    return cfg


def _resolve(value: str | Path, root: Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (root / p).resolve()
