"""Shared helpers for the interpreters."""

from __future__ import annotations

import re
from decimal import Decimal

from esolangs.runtime.source_hints import syntax_error


def parse_integer(source: str) -> int:
    """Parse integer operands without CPython's decimal conversion cap."""
    try:
        return int(source)
    except ValueError:
        if not re.fullmatch(r"[+-]?\d(?:_?\d)*", source):
            raise
        return int(Decimal(source.replace("_", "")))


def format_integer(value: int) -> str:
    """Format an integer without CPython's decimal conversion cap."""
    return str(Decimal(value))


def wrap_int32(value: int) -> int:
    """Wrap ``value`` to a signed 32-bit integer (C ``int`` arithmetic)."""
    return (value + 2**31) % 2**32 - 2**31


def trunc_div(left: int, right: int) -> int:
    """Divide truncating toward zero, as C does, without a float round trip."""
    quotient = abs(left) // abs(right)
    return -quotient if (left < 0) != (right < 0) else quotient


def trunc_mod(left: int, right: int) -> int:
    """Return C's remainder, which takes the dividend's sign."""
    return left - trunc_div(left, right) * right


def parse_int_memory(code: str) -> list[int]:
    """Split ``code`` into a list of whitespace-separated integers.

    ``#`` starts a comment to the end of its line; a non-integer token is a
    malformed program (:class:`ValueError`).
    """
    tokens: list[int] = []
    for line in code.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        for tok in line.split():
            try:
                tokens.append(parse_integer(tok))
            except ValueError:
                raise syntax_error(
                    f"malformed memory token: {tok!r}",
                    "write whitespace-separated decimal integers; # starts a comment",
                ) from None
    return tokens
