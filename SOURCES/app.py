"""CT204 Hybrid Crypto-Steganography — offline Tkinter desktop app (Phase 6A).

Run from ``SOURCES/``:
    .\\.venv\\Scripts\\python.exe app.py            # open the window
    .\\.venv\\Scripts\\python.exe app.py --smoke    # build all tabs, then exit (startup check)
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Must run BEFORE importing src.* (src.crypto compiles @numba.njit(cache=True) at import/use):
# inside a PyInstaller bundle the source folder is read-only/temporary, so point Numba's
# cache to the OS temp folder.
if getattr(sys, "frozen", False):
    _cache_dir = Path(tempfile.gettempdir()) / "ct204_hybrid_crypto_stego_cache"
    _cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(_cache_dir))
else:
    # Allow `python app.py` from any working directory: make SOURCES/ importable.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.ui import launch_app  # noqa: E402  (import after the environment setup above)


def main(argv: list[str] | None = None) -> int:
    return launch_app(argv)


if __name__ == "__main__":
    raise SystemExit(main())
