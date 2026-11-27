"""Chaotic + PRNG masking stream cipher (paper §4.3, Eq. 1–2).

    x_{n+1} = r * x_n * (1 - x_n)                       (Eq. 1, float64)
    chaosMask[n] = clip(floor(x_{n+1} * 256), 0, 255)   (BM-04, starts at x_1, skips x_0)
    eccMask = default_rng(ecc_seed).integers(0, 256, N, uint8)   ("simulated ECC")
    out = S ^ chaosMask ^ eccMask                        (Eq. 2; decrypt == encrypt)
"""

from __future__ import annotations

from typing import Any

import numba
import numpy as np

from src.crypto.base import BaseCipher


@numba.njit(cache=True)
def logistic_mask(x0: float, r: float, n: int) -> np.ndarray:
    """Chaotic uint8 mask of length ``n`` from x_1 .. x_n (BM-04)."""
    out = np.empty(n, dtype=np.uint8)
    x = x0
    for i in range(n):
        x = r * x * (1.0 - x)
        v = int(np.floor(x * 256.0))
        if v < 0:
            v = 0
        elif v > 255:
            v = 255
        out[i] = v
    return out


def ecc_mask(ecc_seed: int, n: int) -> np.ndarray:
    """Simulated ECC key stream: seeded PRNG bytes (no elliptic-curve math, BM-04)."""
    return np.random.default_rng(ecc_seed).integers(0, 256, size=n, dtype=np.uint8)


class ChaoticCipher(BaseCipher):
    def __init__(
        self,
        x0: float,
        r: float,
        ecc_seed: int,
        *,
        cache_mask: bool = False,
    ) -> None:
        x0 = float(x0)
        r = float(r)
        if not 0.0 < x0 < 1.0:
            raise ValueError(f"x0 must be in (0, 1), got {x0}")
        if not 0.0 < r <= 4.0:
            raise ValueError(f"r must be in (0, 4], got {r}")
        self._x0 = x0
        self._r = r
        self._ecc_seed = int(ecc_seed)
        self._cache_mask = bool(cache_mask)
        # BM-10: only populated when cache_mask=True; keyed by the last length N.
        self._cached: tuple[int, np.ndarray] | None = None

    @classmethod
    def from_config(
        cls,
        cfg: dict[str, Any],
        *,
        seed_offset: int = 0,
        cache_mask: bool = False,
    ) -> ChaoticCipher:
        """``seed_offset`` shifts only the ECC seed (``--vary-key-per-image``, BM-03);
        the chaotic parameters x0 and r stay those of the paper."""
        c = cfg["crypto"]["chaotic"]
        return cls(
            c["x0"], c["r"], int(c["ecc_seed"]) + int(seed_offset), cache_mask=cache_mask
        )

    @property
    def name(self) -> str:
        return "chaotic"

    @property
    def x0(self) -> float:
        return self._x0

    @property
    def r(self) -> float:
        return self._r

    @property
    def ecc_seed(self) -> int:
        return self._ecc_seed

    @property
    def cache_mask(self) -> bool:
        return self._cache_mask

    def warmup(self) -> None:
        """Compile the Numba kernel on a 16-byte dummy so JIT time is excluded from EncTime."""
        logistic_mask(self._x0, self._r, 16)

    def combined_mask(self, n: int) -> np.ndarray:
        """``chaosMask ^ eccMask`` of length ``n`` (recomputed unless cache_mask=True)."""
        if self._cache_mask and self._cached is not None and self._cached[0] == n:
            return self._cached[1]
        mask = logistic_mask(self._x0, self._r, n) ^ ecc_mask(self._ecc_seed, n)
        if self._cache_mask:
            self._cached = (n, mask)
        return mask

    def _xor(self, data: bytes) -> bytes:
        n = len(data)
        if n == 0:
            return b""
        buf = np.frombuffer(data, dtype=np.uint8)
        return (buf ^ self.combined_mask(n)).tobytes()

    def encrypt(self, plaintext: bytes) -> bytes:
        return self._xor(plaintext)

    def decrypt(self, ciphertext: bytes) -> bytes:
        return self._xor(ciphertext)
