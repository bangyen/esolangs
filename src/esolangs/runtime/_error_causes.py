"""Transport explicit worker causes with fixed constructors and validated fields."""

from __future__ import annotations

import base64
import decimal
import re
from collections.abc import Iterator

_SIMPLE: dict[str, type[BaseException]] = {
    "ValueError": ValueError,
    "IndexError": IndexError,
    "ZeroDivisionError": ZeroDivisionError,
    "OverflowError": OverflowError,
    "RecursionError": RecursionError,
    "MemoryError": MemoryError,
}
_DECIMAL: dict[str, type[BaseException]] = {
    "DivisionByZero": decimal.DivisionByZero,
    "InvalidOperation": decimal.InvalidOperation,
    "Overflow": decimal.Overflow,
}
_SIGNALS = {**_DECIMAL, "DivisionUndefined": decimal.DivisionUndefined}
_TYPES = {
    **_SIMPLE,
    **_DECIMAL,
    "RegexError": re.error,
    "UnicodeEncodeError": UnicodeEncodeError,
    "UnicodeDecodeError": UnicodeDecodeError,
}
_KINDS = {cls: kind for kind, cls in _TYPES.items()}
_SIGNAL_TAGS = {cls: name for name, cls in _SIGNALS.items()}


def _text(value: object) -> str:
    if type(value) is not str:
        raise ValueError("invalid isolated cause text")
    return value


def _notes(value: object) -> list[str] | None:
    if value is None:
        return None
    if type(value) is not list:
        raise ValueError("invalid isolated cause notes")
    return [_text(item) for item in value]


def _plain_args(args: list[object]) -> list[object]:
    if any(type(arg) not in (int, str) for arg in args):
        raise ValueError("invalid isolated cause arguments")
    return args


def _position(value: object, extent: int) -> int:
    if type(value) is not int or not 0 <= value <= extent:
        raise ValueError("invalid isolated cause position")
    return value


def _regex_args(args: list[object]) -> tuple[str, str | None, int | None]:
    if len(args) != 3:
        raise ValueError("invalid isolated regex cause")
    message, pattern, offset = args
    if offset is None:
        return _text(message), None if pattern is None else _text(pattern), None
    pattern = _text(pattern)
    return _text(message), pattern, _position(offset, len(pattern))


def _unicode_args(args: list[object]) -> tuple[str, str, int, int, str]:
    if len(args) != 5:
        raise ValueError("invalid isolated Unicode cause")
    encoding, value, start, end, reason = args
    text = _text(value)
    first, last = _position(start, len(text)), _position(end, len(text))
    if last < first:
        raise ValueError("invalid isolated Unicode cause range")
    return _text(encoding), text, first, last, _text(reason)


def _decode_unicode(args: list[object]) -> UnicodeDecodeError:
    encoding, encoded, start, end, reason = _unicode_args(args)
    data = base64.b64decode(encoded, validate=True)
    if end > len(data):
        raise ValueError("invalid isolated Unicode cause range")
    return UnicodeDecodeError(encoding, data, start, end, reason)


def _decimal_signals(args: list[object]) -> list[type[BaseException]]:
    if len(args) != 1 or type(args[0]) is not list:
        raise ValueError("invalid isolated Decimal cause")
    signals = []
    for tag in args[0]:
        if type(tag) is not str or tag not in _SIGNALS:
            raise ValueError("invalid isolated Decimal signal")
        signals.append(_SIGNALS[tag])
    return signals


def _encode_args(cause: BaseException, kind: str) -> list[object]:
    if isinstance(cause, re.error):
        return list(_regex_args([cause.msg, cause.pattern, cause.pos]))
    if isinstance(cause, UnicodeDecodeError):
        encoded = base64.b64encode(cause.object).decode("ascii")
        args = _unicode_args(
            [cause.encoding, encoded, cause.start, cause.end, cause.reason]
        )
        if args[3] > len(cause.object):
            raise ValueError("invalid isolated Unicode cause range")
        return list(args)
    if isinstance(cause, UnicodeEncodeError):
        return list(_unicode_args(list(cause.args)))
    if kind in _DECIMAL:
        if len(cause.args) != 1 or type(cause.args[0]) is not list:
            raise ValueError("invalid isolated Decimal cause")
        signals = cause.args[0]
        if any(type(signal) is not type for signal in signals):
            raise ValueError("invalid isolated Decimal signals")
        return [[_SIGNAL_TAGS[signal] for signal in signals]]
    return _plain_args(list(cause.args))


def cause_chain(cause: BaseException | None) -> Iterator[BaseException]:
    """Follow explicit causes without looping through a cycle."""
    seen: set[int] = set()
    while cause is not None and id(cause) not in seen:
        yield cause
        seen.add(id(cause))
        cause = cause.__cause__


def encode_cause(cause: BaseException | None) -> list[dict[str, object]] | None:
    """Retain the supported prefix of an explicit cause chain."""
    chain: list[dict[str, object]] = []
    for error in cause_chain(cause):
        kind = _KINDS.get(type(error))
        if kind is None:
            break
        try:
            args = _encode_args(error, kind)
            notes = _notes(getattr(error, "__notes__", None))
        except (KeyError, TypeError, ValueError):
            break
        chain.append(
            {
                "kind": kind,
                "args": args,
                "notes": notes,
                "suppress_context": error.__suppress_context__,
            }
        )
    return chain or None


def _decode_node(value: object, nested: BaseException | None) -> BaseException:
    if type(value) is not dict or value.keys() != {
        "kind",
        "args",
        "notes",
        "suppress_context",
    }:
        raise ValueError("invalid isolated cause record")
    kind, args = value["kind"], value["args"]
    suppressed = value["suppress_context"]
    if type(kind) is not str or type(args) is not list or type(suppressed) is not bool:
        raise ValueError("invalid isolated cause fields")
    cause: BaseException
    if kind in _SIMPLE:
        cause = _SIMPLE[kind](*_plain_args(args))
    elif kind == "RegexError":
        cause = re.error(*_regex_args(args))
    elif kind == "UnicodeEncodeError":
        cause = UnicodeEncodeError(*_unicode_args(args))
    elif kind == "UnicodeDecodeError":
        cause = _decode_unicode(args)
    elif kind in _DECIMAL:
        cause = _DECIMAL[kind](_decimal_signals(args))
    else:
        raise ValueError("unknown isolated cause kind")
    notes = _notes(value["notes"])
    if notes is not None:
        cause.__notes__ = notes
    cause.__cause__ = nested
    cause.__suppress_context__ = suppressed
    return cause


def decode_cause(value: object) -> BaseException | None:
    """Restore only explicitly supported, validated cause records."""
    cause = None
    if value is not None:
        if type(value) is not list or not value:
            raise ValueError("invalid isolated cause chain")
        for record in reversed(value):
            cause = _decode_node(record, cause)
    return cause
