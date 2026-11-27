"""Strategy interface for the cryptography layer and shared helpers.

Design decisions (see Plans/03_TECHNICAL_BLIND_SPOTS_AND_DECISIONS.md):
- BM-03: keys/IVs are derived deterministically with SHA-256 domain separation.
- BM-05: ciphertexts keep full PKCS#7 padding; only the *image view* is truncated.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import numpy as np


class BaseCipher(ABC):
    """Abstract cipher used by the pipeline (Strategy pattern)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical name: '3des' | 'aes' | 'chaotic'."""

    @property
    def block_size(self) -> int | None:
        """Block size in bytes (8 for 3DES, 16 for AES, None for stream ciphers)."""
        return None

    @abstractmethod
    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt ``plaintext`` and return the ciphertext bytes."""

    @abstractmethod
    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt ``ciphertext`` and return the original plaintext bytes."""

    def warmup(self) -> None:
        """Pre-run hook before timing EncTime (compiles Numba JIT for ChaoticCipher)."""
        return None

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"


def derive_bytes(seed: int, length: int, label: str) -> bytes:
    """Deterministic, domain-separated byte string (BM-03).

    ``SHA-256(f"{seed}:{label}")`` seeds a NumPy PCG64 generator, so different labels
    (e.g. ``"aes:key"`` vs ``"3des:key:0"``) yield statistically independent bytes.
    """
    if length < 0:
        raise ValueError(f"length must be >= 0, got {length}")
    digest = hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest, "big"))
    return rng.integers(0, 256, size=length, dtype=np.uint8).tobytes()


def ciphertext_to_image_view(ciphertext: bytes, secret_shape: tuple[int, int]) -> np.ndarray:
    """2D ``uint8`` view of a ciphertext for display and NPCR/UACI/correlation (BM-05).

    Keeps exactly the first ``H_s * W_s`` bytes (drops trailing PKCS#7 bytes) and never
    pads artificial values. The full ciphertext must still be embedded for decryption.
    """
    h, w = (int(v) for v in secret_shape)
    if h <= 0 or w <= 0:
        raise ValueError(f"secret_shape must be positive, got {secret_shape}")
    n = h * w
    if len(ciphertext) < n:
        raise ValueError(
            f"ciphertext has {len(ciphertext)} bytes, fewer than H_s*W_s = {n}"
        )
    return np.frombuffer(ciphertext, dtype=np.uint8, count=n).reshape(h, w).copy()
