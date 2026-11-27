"""3DES-192 (EDE, 3-key) in CBC mode with PKCS#7 padding (paper §4.1)."""

from __future__ import annotations

from typing import Any

from Crypto.Cipher import DES3
from Crypto.Util.Padding import pad, unpad

from src.crypto.base import BaseCipher, derive_bytes

KEY_BYTES = 24
IV_BYTES = 8
BLOCK_BYTES = 8
_MAX_KEY_ATTEMPTS = 64


class DES3Cipher(BaseCipher):
    def __init__(self, key: bytes, iv: bytes) -> None:
        if len(key) != KEY_BYTES:
            raise ValueError(f"3DES key must be {KEY_BYTES} bytes, got {len(key)}")
        if len(iv) != IV_BYTES:
            raise ValueError(f"3DES IV must be {IV_BYTES} bytes, got {len(iv)}")
        # Raises ValueError for degenerate keys (K1 == K2 or K2 == K3), which would
        # silently collapse 3DES to single DES.
        adjusted = DES3.adjust_key_parity(bytes(key))
        DES3.new(adjusted, DES3.MODE_CBC, iv=bytes(iv))
        self._key = adjusted
        self._iv = bytes(iv)

    @classmethod
    def from_config(cls, cfg: dict[str, Any], *, seed_offset: int = 0) -> DES3Cipher:
        crypto = cfg["crypto"]
        _check_sizes(crypto.get("des3", {}))
        seed = int(crypto["key_seed"]) + int(seed_offset)
        iv = derive_bytes(seed, IV_BYTES, "3des:iv")
        for attempt in range(_MAX_KEY_ATTEMPTS):
            key = derive_bytes(seed, KEY_BYTES, f"3des:key:{attempt}")
            try:
                return cls(key, iv)
            except ValueError:
                continue  # degenerate key: derive the next candidate
        raise RuntimeError(f"no non-degenerate 3DES key after {_MAX_KEY_ATTEMPTS} attempts")

    @property
    def name(self) -> str:
        return "3des"

    @property
    def block_size(self) -> int:
        return BLOCK_BYTES

    @property
    def key(self) -> bytes:
        return self._key

    @property
    def iv(self) -> bytes:
        return self._iv

    def _new(self):
        # Fresh CBC object per call: CBC objects are stateful and single-use.
        return DES3.new(self._key, DES3.MODE_CBC, iv=self._iv)

    def encrypt(self, plaintext: bytes) -> bytes:
        return self._new().encrypt(pad(plaintext, BLOCK_BYTES, style="pkcs7"))

    def decrypt(self, ciphertext: bytes) -> bytes:
        if len(ciphertext) == 0 or len(ciphertext) % BLOCK_BYTES != 0:
            raise ValueError(
                f"3DES ciphertext length must be a positive multiple of {BLOCK_BYTES}, "
                f"got {len(ciphertext)}"
            )
        return unpad(self._new().decrypt(ciphertext), BLOCK_BYTES, style="pkcs7")


def _check_sizes(section: dict[str, Any]) -> None:
    key_bytes = int(section.get("key_bytes", KEY_BYTES))
    iv_bytes = int(section.get("iv_bytes", IV_BYTES))
    if (key_bytes, iv_bytes) != (KEY_BYTES, IV_BYTES):
        raise ValueError(
            f"crypto.des3 must be key_bytes={KEY_BYTES}, iv_bytes={IV_BYTES}; "
            f"got {key_bytes}, {iv_bytes}"
        )
