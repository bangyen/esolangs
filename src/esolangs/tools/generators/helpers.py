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


def _cm_constants(maxval: int) -> list[str]:
    """Lines building Collatz Multiverse constants ``k1..kmaxval``.

    ``k1``/``k2`` are bootstrapped from ``negativeOne``, then the copy trick
    ``v = negativeOne x + k`` sets a fresh register to any already built
    constant, and ``v = one x + one`` (from the odd ``n-1``) and ``v = one x
    + two`` (from the odd ``n-2``) reach every larger value in two lines.
    """
    lines = [
        "k1 = negativeOne x + negativeOne, NOT PRINT.",
        "k1 = negativeOne x + zero, NOT PRINT.",
        "k2 = negativeOne x + negativeOne, NOT PRINT.",
        "k2 = negativeOne x + k1, NOT PRINT.",
    ]
    for n in range(3, maxval + 1):
        v = n - 1 if n % 2 == 0 else n - 2
        b = "k1" if n % 2 == 0 else "k2"
        lines.append(f"k{n} = negativeOne x + k{v}, NOT PRINT.")
        lines.append(f"k{n} = k1 x + {b}, NOT PRINT.")
    return lines
