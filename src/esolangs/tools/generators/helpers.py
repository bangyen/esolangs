"""Shared helpers for the text generators."""


def _ilog(base: int, n: int) -> int:
    """Floor of log_base(n), computed with integers to avoid float error."""
    k = 0
    while base ** (k + 1) <= n:
        k += 1
    return k


def _require_bytes(text: str, name: str) -> None:
    """Reject any character outside the 0-255 byte range.

    The byte-oriented reference interpreters emit one byte per character, so
    a generator that builds byte values would silently corrupt codepoints
    above 255.  Fail loudly instead.
    """
    if any(ord(c) > 255 for c in text):
        raise ValueError(f"{name} can only output bytes 0-255")


def _require_ascii(text: str, name: str) -> None:
    """Reject any character outside the 0-127 ASCII range.

    Some interpreters keep a 7-bit accumulator or parity, so values above 127
    wrap and would be printed as the wrong byte.  Fail loudly instead.
    """
    if any(ord(c) > 127 for c in text):
        raise ValueError(f"{name} can only output ASCII (0-127)")
