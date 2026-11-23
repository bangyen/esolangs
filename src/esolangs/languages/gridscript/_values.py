"""GridScript primitive values, numeric conversions and arithmetic."""

import math
import re
import struct
from typing import NamedTuple

from esolangs.exceptions import HaltError
from esolangs.runtime.memory import format_integer, parse_integer

_INT = re.compile(r"[+-]?\d+")
_FLOAT = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?")


_INT_MIN, _INT_MAX = -(2**31), 2**31 - 1


class _Null:
    """GridScript's NULL: unassigned, end of input, a failed cast."""

    def __repr__(self) -> str:
        return "NULL"


NULL = _Null()


class _Float(NamedTuple):
    """A 32-bit FLOAT, kept apart from INT."""

    value: float


type _Value = int | _Float | str | bool | _Null


def _f16(value: float) -> float:
    return float(struct.unpack("e", struct.pack("e", value))[0])


def _f32(value: float) -> float:
    try:
        return float(struct.unpack("f", struct.pack("f", value))[0])
    except OverflowError:
        return math.copysign(math.inf, value)


def _int(value: int) -> int:
    if not _INT_MIN <= value <= _INT_MAX:
        raise HaltError(f"{format_integer(value)} overflows a 32-bit INT")
    return value


def _number(value: _Value) -> int | _Float | None:
    """Cast to INT or FLOAT, or None when the value cannot be cast."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, _Float)):
        return value
    if isinstance(value, _Null):
        return 0
    text = value.strip()
    if not text:
        return 0
    if _INT.fullmatch(text):
        number = parse_integer(text)
        return number if _INT_MIN <= number <= _INT_MAX else None
    if _FLOAT.fullmatch(text):
        return _Float(_f32(float(text)))
    return None


def _to_int(value: _Value) -> int | None:
    number = _number(value)
    if number is None:
        return None
    if isinstance(number, _Float):
        if not math.isfinite(number.value):
            return None
        number = math.trunc(number.value)
        return number if _INT_MIN <= number <= _INT_MAX else None
    return number


def _to_bool(value: _Value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, _Null):
        return False
    if isinstance(value, str):
        return value not in ("", "0")
    if isinstance(value, _Float):
        return value.value != 0
    return value != 0


def _show_float(value: float) -> str:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    for digits in range(1, 10):
        text = f"{value:.{digits}g}"
        if _f32(float(text)) == value:
            break
    if "e" not in text and "." not in text:
        text += ".0"
    return text


def _to_str(value: _Value) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, _Null):
        return ""
    if isinstance(value, _Float):
        return _show_float(value.value)
    return str(value)


def _cast(value: _Value, typ: str) -> _Value:
    """Cast to a named type; NULL when it cannot be (a silent warning)."""
    if typ == "STRING":
        return _to_str(value)
    if typ == "BOOL":
        return _to_bool(value)
    if typ == "INT":
        got = _to_int(value)
        return NULL if got is None else got
    number = _number(value)
    if number is None:
        return NULL
    return number if isinstance(number, _Float) else _Float(_f32(float(number)))


def _arith(verb: str, a: _Value, b: _Value) -> int | _Float:
    x, y = _number(a), _number(b)
    if x is None or y is None:
        raise HaltError(f"{verb} needs numbers, got {a!r} and {b!r}")
    if isinstance(x, int) and isinstance(y, int):
        if verb == "INCREMENT":
            return _int(x + y)
        if verb == "DECREMENT":
            return _int(x - y)
        if verb == "MULTIPLY":
            return _int(x * y)
        if y == 0:
            raise HaltError("DIVIDE by zero")
        q = abs(x) // abs(y)
        return _int(q if (x < 0) == (y < 0) else -q)
    fx = x.value if isinstance(x, _Float) else float(x)
    fy = y.value if isinstance(y, _Float) else float(y)
    if verb == "INCREMENT":
        return _Float(_f32(fx + fy))
    if verb == "DECREMENT":
        return _Float(_f32(fx - fy))
    if verb == "MULTIPLY":
        return _Float(_f32(fx * fy))
    if fy == 0:
        raise HaltError("DIVIDE by zero")
    return _Float(_f32(fx / fy))
