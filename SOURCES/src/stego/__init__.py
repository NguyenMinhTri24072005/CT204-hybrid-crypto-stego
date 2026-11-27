"""Steganography layer: vectorized multi-LSB embedding with a 16-byte header."""

from src.stego.lsb import EmbedResult, embed, extract

__all__ = ["EmbedResult", "embed", "extract"]
