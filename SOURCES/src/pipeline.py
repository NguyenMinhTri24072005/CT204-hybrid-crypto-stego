"""End-to-end pipeline: image I/O + crypto + LSB stego + visual/security metrics.

    secret (H_s, W_s) uint8 -> tobytes (C-order) -> cipher.encrypt -> embed -> stego .png
    stego .png -> extract -> cipher.decrypt -> reshape (H_s, W_s) -> recovered secret

All arrays are RGB / C-order inside the program (BM-02); BGR <-> RGB conversion happens only
in the I/O helpers. Images are read/written via ``cv2.imdecode``/``imencode`` so Windows
paths with spaces or non-ASCII characters work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.crypto import BaseCipher, ciphertext_to_image_view, create_cipher
from src.metrics import compute_all_metrics, measure_enc_time
from src.stego.lsb import EmbedResult, embed, extract

LOSSLESS_SUFFIX = ".png"
MATLAB_COINS_SHAPE = (246, 300)  # BM-01: H=246, W=300


# ------------------------------------------------------------------------------- I/O
def _read(path: str | Path, flags: int) -> np.ndarray:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), flags)
    if img is None:
        raise ValueError(f"cannot decode image: {path}")
    return img


def read_rgb(path: str | Path, size: tuple[int, int] | None = None) -> np.ndarray:
    """Read a colour image as (H, W, 3) uint8 RGB; optionally resize to ``size=(H, W)``."""
    img = cv2.cvtColor(_read(path, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    if size is not None and tuple(img.shape[:2]) != tuple(size):
        img = cv2.resize(img, (int(size[1]), int(size[0])), interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(img, dtype=np.uint8)


def read_gray(path: str | Path, size: tuple[int, int] | None = None) -> np.ndarray:
    """Read a grayscale secret as (H, W) uint8; optionally resize to ``size=(H, W)`` (BM-01)."""
    img = _read(path, cv2.IMREAD_GRAYSCALE)
    if size is not None and tuple(img.shape[:2]) != tuple(size):
        img = cv2.resize(img, (int(size[1]), int(size[0])), interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(img, dtype=np.uint8)


def save_stego_png(path: str | Path, stego_rgb: np.ndarray) -> Path:
    """Write the stego image losslessly. Any non-.png suffix (e.g. .jpg) raises ValueError."""
    path = Path(path)
    if path.suffix.lower() != LOSSLESS_SUFFIX:
        raise ValueError(f"stego images must be saved as lossless .png, got {path.name!r}")
    stego = np.asarray(stego_rgb)
    if stego.dtype != np.uint8 or stego.ndim != 3 or stego.shape[2] != 3:
        raise ValueError(f"stego must be (H, W, 3) uint8, got {stego.shape} {stego.dtype}")
    ok, buf = cv2.imencode(LOSSLESS_SUFFIX, cv2.cvtColor(stego, cv2.COLOR_RGB2BGR))
    if not ok:
        raise ValueError(f"PNG encoding failed for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    buf.tofile(path)
    return path


def save_gray_png(path: str | Path, gray: np.ndarray) -> Path:
    """Write a 2D uint8 grayscale image as lossless .png (Unicode-safe on Windows)."""
    path = Path(path)
    if path.suffix.lower() != LOSSLESS_SUFFIX:
        raise ValueError(f"grayscale images must be saved as .png, got {path.name!r}")
    arr = np.asarray(gray)
    if arr.dtype != np.uint8 or arr.ndim != 2:
        raise ValueError(f"grayscale image must be (H, W) uint8, got {arr.shape} {arr.dtype}")
    ok, buf = cv2.imencode(LOSSLESS_SUFFIX, np.ascontiguousarray(arr, dtype=np.uint8))
    if not ok:
        raise ValueError(f"PNG encoding failed for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    buf.tofile(path)
    return path


def ensure_secret_gray(secret_path: str | Path, size: tuple[int, int] | None = None) -> np.ndarray:
    """Load grayscale secret; if missing on disk, synthesize MATLAB 246x300 coins (BM-01)."""
    path = Path(secret_path)
    if not path.is_file():
        from skimage import data as skdata

        coins = cv2.resize(
            skdata.coins(),
            (MATLAB_COINS_SHAPE[1], MATLAB_COINS_SHAPE[0]),
            interpolation=cv2.INTER_AREA,
        )
        save_gray_png(path, coins)
    return read_gray(path, size=size)


# ---------------------------------------------------------------------- crypto+stego
def _secret_bytes(secret: np.ndarray) -> bytes:
    secret = np.asarray(secret)
    if secret.dtype != np.uint8 or secret.ndim != 2:
        raise ValueError(f"secret must be a 2D uint8 array, got {secret.shape} {secret.dtype}")
    return np.ascontiguousarray(secret).tobytes()


def hide(
    secret: np.ndarray,
    cover_rgb: np.ndarray,
    cipher: BaseCipher,
    *,
    max_lsb: int = 3,
    interpolation: str = "cubic",
) -> tuple[bytes, EmbedResult]:
    """Encrypt the secret and embed the full ciphertext; returns ``(ciphertext, EmbedResult)``."""
    ciphertext = cipher.encrypt(_secret_bytes(secret))
    result = embed(
        cover_rgb, ciphertext, secret.shape, max_lsb=max_lsb, interpolation=interpolation
    )
    return ciphertext, result


def reveal(stego_rgb: np.ndarray, cipher: BaseCipher) -> np.ndarray:
    """Recover the secret from the stego image and the cipher only (blind extraction)."""
    ciphertext, (h, w), _ = extract(stego_rgb)
    plaintext = cipher.decrypt(ciphertext)
    if len(plaintext) != h * w:
        raise ValueError(f"decrypted {len(plaintext)} bytes, expected H_s*W_s = {h * w}")
    return np.frombuffer(plaintext, dtype=np.uint8).reshape(h, w).copy()


@dataclass
class PipelineResult:
    cipher_name: str
    secret: np.ndarray  # (H_s, W_s) uint8
    ciphertext: bytes  # full ciphertext incl. PKCS#7 padding
    encrypted_view: np.ndarray  # (H_s, W_s) uint8 view of the ciphertext (BM-05)
    embed: EmbedResult  # stego_rgb, cover_used_rgb, num_lsb, was_scaled_up, ...
    stego_rgb: np.ndarray  # image actually decoded (re-read from disk when saved)
    recovered: np.ndarray  # (H_s, W_s) uint8
    stego_path: Path | None = None
    enc_time_s: float = 0.0
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def cover_used_rgb(self) -> np.ndarray:
        return self.embed.cover_used_rgb

    @property
    def is_exact(self) -> bool:
        """True when the recovered secret is bit-identical to the original (MSE == 0)."""
        return self.recovered.shape == self.secret.shape and np.array_equal(
            self.recovered, self.secret
        )


def run_pipeline(
    secret: np.ndarray,
    cover_rgb: np.ndarray,
    cipher: BaseCipher,
    *,
    max_lsb: int = 3,
    interpolation: str = "cubic",
    stego_path: str | Path | None = None,
    compute_metrics: bool = True,
    warmup: bool = True,
) -> PipelineResult:
    """encrypt (timed) -> embed -> (save .png -> reload) -> extract -> decrypt -> metrics."""
    plaintext = _secret_bytes(secret)
    ciphertext, enc_time_s = measure_enc_time(cipher, plaintext, warmup=warmup)
    result = embed(
        cover_rgb, ciphertext, secret.shape, max_lsb=max_lsb, interpolation=interpolation
    )
    stego = result.stego_rgb
    saved: Path | None = None
    if stego_path is not None:
        saved = save_stego_png(stego_path, stego)
        stego = read_rgb(saved)
    recovered = reveal(stego, cipher)
    encrypted_view = ciphertext_to_image_view(ciphertext, secret.shape)
    metrics = (
        compute_all_metrics(
            secret,
            encrypted_view,
            result.cover_used_rgb,
            stego,
            enc_time_s=enc_time_s,
        )
        if compute_metrics
        else {}
    )
    return PipelineResult(
        cipher_name=cipher.name,
        secret=secret,
        ciphertext=ciphertext,
        encrypted_view=encrypted_view,
        embed=result,
        stego_rgb=stego,
        recovered=recovered,
        stego_path=saved,
        enc_time_s=enc_time_s,
        metrics=metrics,
    )


def run_from_config(
    cfg: dict[str, Any],
    cipher_name: str,
    *,
    cover_path: str | Path | None = None,
    secret_path: str | Path | None = None,
    secret_size: tuple[int, int] | None = None,
    stego_path: str | Path | None = None,
    seed_offset: int = 0,
    cache_chaotic_mask: bool = False,
    compute_metrics: bool = True,
    warmup: bool = True,
) -> PipelineResult:
    """Run the pipeline with defaults from config (cover: ``paths.sample_dir/cover.jpg``;
    secret: ``secret.path`` resized to ``secret_size`` or ``secret.resize``)."""
    stego_cfg = cfg["stego"]
    cover_path = cover_path or Path(cfg["paths"]["sample_dir"]) / "cover.jpg"
    secret_path = secret_path or cfg["secret"]["path"]
    size = secret_size or cfg["secret"].get("resize")
    cover = read_rgb(cover_path, size=tuple(stego_cfg["cover_size"]))
    secret = read_gray(secret_path, size=tuple(size) if size else None)
    cipher = create_cipher(
        cipher_name, cfg, seed_offset=seed_offset, cache_chaotic_mask=cache_chaotic_mask
    )
    return run_pipeline(
        secret,
        cover,
        cipher,
        max_lsb=int(stego_cfg["max_lsb"]),
        interpolation=str(stego_cfg.get("scale_up_interpolation", "cubic")),
        stego_path=stego_path,
        compute_metrics=compute_metrics,
        warmup=warmup,
    )
