"""Input containers normalized without imposing a language input unit."""

from __future__ import annotations

from typing import IO

from esolangs.exceptions import ArgumentError, EsolangError
from esolangs.runtime._files import read_snapshot
from esolangs.runtime.source_hints import with_hint

#: A stream is consumed from its current position.  Spelled with ``typing.IO``
#: so the public alias names no private type; at runtime any ``.read()`` does.
type InputSource = str | bytes | IO[str] | IO[bytes]


def check_input(source: InputSource) -> None:
    """Check the input container without consuming a stream."""
    if isinstance(source, (str, bytes)):
        return
    try:
        reader = getattr(source, "read", None)
    except EsolangError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise _read_failed(exc) from exc
    if not callable(reader):
        raise with_hint(
            ArgumentError(
                "stdin must be a string, bytes, or a readable stream, got "
                f"{type(source).__name__}"
            ),
            ("to read a file, pass its open stream or its UTF-8 text contents"),
        )


def _read_failed(error: Exception) -> ArgumentError:
    return with_hint(
        ArgumentError(f"cannot read stdin: {error}"),
        ("open the input stream for reading and encode binary input as UTF-8"),
    )


def read_input(source: InputSource) -> str:
    """Snapshot remaining input; binary input is UTF-8 text."""
    check_input(source)
    try:
        value = source if isinstance(source, (str, bytes)) else read_snapshot(source)
        if isinstance(value, bytes):
            return bytes.decode(value, "utf-8")
        if isinstance(value, str):
            return str.__str__(value)
    except EsolangError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise _read_failed(exc) from exc
    raise with_hint(
        ArgumentError("stdin stream must return a string or bytes"),
        (
            "make stream.read() return text or UTF-8 "
            "bytes; alternatively pass the contents "
            "directly"
        ),
    )
