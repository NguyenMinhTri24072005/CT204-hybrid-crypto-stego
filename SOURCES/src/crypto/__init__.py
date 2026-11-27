"""Cryptography layer (Strategy pattern) and cipher factory."""

from __future__ import annotations

from typing import Any

from src.crypto.aes_cipher import AESCipher
from src.crypto.base import BaseCipher, ciphertext_to_image_view, derive_bytes
from src.crypto.chaotic_cipher import ChaoticCipher
from src.crypto.des3_cipher import DES3Cipher

CIPHER_NAMES: tuple[str, ...] = ("3des", "aes", "chaotic")
_ALIASES = {"3des": "3des", "des3": "3des", "aes": "aes", "chaotic": "chaotic"}


def create_cipher(
    name: str,
    cfg: dict[str, Any],
    *,
    seed_offset: int = 0,
    cache_chaotic_mask: bool = False,
) -> BaseCipher:
    """Build a cipher from its name ('3des' | 'des3' | 'aes' | 'chaotic') and config."""
    canonical = _ALIASES.get(str(name).strip().lower())
    if canonical is None:
        raise ValueError(f"unknown cipher {name!r}; expected one of {sorted(_ALIASES)}")
    if canonical == "3des":
        return DES3Cipher.from_config(cfg, seed_offset=seed_offset)
    if canonical == "aes":
        return AESCipher.from_config(cfg, seed_offset=seed_offset)
    return ChaoticCipher.from_config(cfg, seed_offset=seed_offset, cache_mask=cache_chaotic_mask)


__all__ = [
    "AESCipher",
    "BaseCipher",
    "CIPHER_NAMES",
    "ChaoticCipher",
    "DES3Cipher",
    "ciphertext_to_image_view",
    "create_cipher",
    "derive_bytes",
]
