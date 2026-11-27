"""Configuration loading for the crypto-steganography pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "default.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load a YAML config and resolve every entry under ``paths`` (and ``secret.path``)
    to an absolute path relative to the project root (``SOURCES/``)."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with open(config_path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f) or {}

    for key, value in cfg.get("paths", {}).items():
        cfg["paths"][key] = _resolve(value)
    secret = cfg.get("secret")
    if secret and secret.get("path"):
        secret["path"] = _resolve(secret["path"])
    return cfg


def _resolve(value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()
