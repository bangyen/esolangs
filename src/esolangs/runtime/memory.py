"""Shared helpers for the interpreters."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import Field
from decimal import Decimal
from fractions import Fraction
from typing import cast

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


#: CPython's int/str digit-cap ValueError, an implementation limit.  Matched
#: from the start: a parse error echoing source "Exceeds the limit (" is not.
_DIGIT_CAP = re.compile(r"Exceeds the limit \(\d+ digits\) for integer string")


def _hit_digit_cap(error: BaseException | None) -> bool:
    """Whether CPython's digit cap raised ``error`` or anything it chains."""
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        if isinstance(error, ValueError) and _DIGIT_CAP.match(str(error)):
            return True
        seen.add(id(error))
        error = error.__cause__ or error.__context__
    return False


_CONTAINERS = (dict, list, tuple, set, frozenset)
_PRIMITIVES = (int, bool, str, bytes, bytearray, float, complex, Fraction, type(None))
type _Container = (
    dict[object, object]
    | list[object]
    | tuple[object, ...]
    | set[object]
    | frozenset[object]
)


def _plain_repr(value: object, seen: set[int]) -> bool:
    """Refuse to repeat a custom repr after a surrounding builtin repr failed."""
    if any(type(value) is kind for kind in _PRIMITIVES):
        return True
    if not any(type(value) is kind for kind in _CONTAINERS):
        return False
    if id(value) in seen:
        return True
    seen.add(id(value))
    if isinstance(value, dict):
        return all(
            _plain_repr(k, seen) and _plain_repr(v, seen) for k, v in value.items()
        )
    return all(_plain_repr(item, seen) for item in cast(_Container, value))


def _container_repr(value: _Container, render: Callable[[object], str]) -> str:
    """Render only exact builtin containers; preserve their punctuation and order."""
    if isinstance(value, dict):
        return (
            "{"
            + ", ".join(render(k) + ": " + render(v) for k, v in value.items())
            + "}"
        )
    shown = ", ".join(map(render, value))
    if isinstance(value, list):
        return "[" + shown + "]"
    if isinstance(value, tuple):
        return "(" + shown + ("," if len(value) == 1 else "") + ")"
    return (
        "frozenset({" + shown + "})"
        if isinstance(value, frozenset)
        else "{" + shown + "}"
    )


def _repr_value(
    value: object, format_large_int: Callable[[int], str], active: set[int] | None
) -> str:
    try:
        return repr(value)
    except ValueError as error:
        if not _hit_digit_cap(error) or (
            active is None and not _plain_repr(value, set())
        ):
            raise
    if type(value) is int:
        return format_large_int(value)
    if type(value) is Fraction:
        numerator = _repr_value(value.numerator, format_large_int, active)
        denominator = _repr_value(value.denominator, format_large_int, active)
        return f"Fraction({numerator}, {denominator})"
    if active is None:
        active = set()
    if id(value) in active:
        markers: dict[type[object], str] = {
            list: "[...]",
            dict: "{...}",
            tuple: "(...)",
        }
        return markers.get(type(value), "...")
    active.add(id(value))
    try:
        return _container_repr(
            cast(_Container, value),
            lambda item: _repr_value(item, format_large_int, active),
        )
    finally:
        active.remove(id(value))


def repr_value(value: object, *, format_large_int: Callable[[int], str] = hex) -> str:
    """Keep ordinary repr and fall back for capped integers in plain values."""
    return _repr_value(value, format_large_int, None)


def repr_record(record: object, fields: Iterable[Field[object]]) -> str:
    """Keep dataclass field order and render large integers in each value."""
    values = ", ".join(
        f"{field.name}={repr_value(getattr(record, field.name))}"
        for field in fields
        if field.repr
    )
    return f"{type(record).__qualname__}({values})"


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
    for raw_line in code.splitlines():
        line = raw_line.split("#", 1)[0].strip()
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
