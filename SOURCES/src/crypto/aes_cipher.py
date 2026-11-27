"""AES-128 in CBC mode with PKCS#7 padding (paper §4.2)."""

from __future__ import annotations

from typing import Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from src.crypto.base import BaseCipher, derive_bytes

KEY_BYTES = 16
IV_BYTES = 16
BLOCK_BYTES = 16


class AESCipher(BaseCipher):
    def __init__(self, key: bytes, iv: bytes) -> None:
        if len(key) != KEY_BYTES:
            raise ValueError(f"AES-128 key must be {KEY_BYTES} bytes, got {len(key)}")
        if len(iv) != IV_BYTES:
            raise ValueError(f"AES IV must be {IV_BYTES} bytes, got {len(iv)}")
        self._key = bytes(key)
        self._iv = bytes(iv)

    @classmethod
    def from_config(cls, cfg: dict[str, Any], *, seed_offset: int = 0) -> AESCipher:
        crypto = cfg["crypto"]
        section = crypto.get("aes", {})
        key_bytes = int(section.get("key_bytes", KEY_BYTES))
        iv_bytes = int(section.get("iv_bytes", IV_BYTES))
        if (key_bytes, iv_bytes) != (KEY_BYTES, IV_BYTES):
            raise ValueError(
                f"crypto.aes must be key_bytes={KEY_BYTES}, iv_bytes={IV_BYTES}; "
                f"got {key_bytes}, {iv_bytes}"
            )
        seed = int(crypto["key_seed"]) + int(seed_offset)
        return cls(derive_bytes(seed, KEY_BYTES, "aes:key"), derive_bytes(seed, IV_BYTES, "aes:iv"))

    @property
    def name(self) -> str:
        return "aes"

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
        return AES.new(self._key, AES.MODE_CBC, iv=self._iv)

    def encrypt(self, plaintext: bytes) -> bytes:
        return self._new().encrypt(pad(plaintext, BLOCK_BYTES, style="pkcs7"))

    def decrypt(self, ciphertext: bytes) -> bytes:
        if len(ciphertext) == 0 or len(ciphertext) % BLOCK_BYTES != 0:
            raise ValueError(
                f"AES ciphertext length must be a positive multiple of {BLOCK_BYTES}, "
                f"got {len(ciphertext)}"
            )
        return unpad(self._new().decrypt(ciphertext), BLOCK_BYTES, style="pkcs7")
