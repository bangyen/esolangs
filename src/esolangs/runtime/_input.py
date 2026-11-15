"""Input containers normalized without imposing a language input unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import IO

from esolangs.exceptions import ArgumentError, EsolangError
from esolangs.outcomes import _remember_acquisition_failure
from esolangs.runtime._files import read_snapshot
from esolangs.runtime.source_hints import with_hint

#: A stream is consumed from its current position.  Spelled with ``typing.IO``
#: so the public alias names no private type; at runtime any ``.read()`` does.
type InputSource = str | bytes | IO[str] | IO[bytes]


@dataclass(frozen=True, slots=True)
class _BoundReader:
    """Keep the checked reader and the stream that owns its descriptor."""

    stream: IO[str] | IO[bytes]
    read: Callable[..., str | bytes | None]


type CheckedInput = str | bytes | _BoundReader


def check_input(source: InputSource) -> CheckedInput:
    """Bind the input reader without consuming a stream."""
    if isinstance(source, (str, bytes)):
        return source
    try:
        reader = getattr(source, "read", None)
    except EsolangError as error:
        _remember_acquisition_failure(error)
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
    return _BoundReader(source, reader)


def _read_failed(error: Exception) -> ArgumentError:
    return with_hint(
        ArgumentError(f"cannot read stdin: {error}"),
        ("open the input stream for reading and encode binary input as UTF-8"),
    )


def read_input(source: InputSource | CheckedInput) -> str:
    """Snapshot remaining input; binary input is UTF-8 text."""
    bound = source if isinstance(source, _BoundReader) else check_input(source)
    try:
        value = (
            read_snapshot(bound.stream, reader=bound.read)
            if isinstance(bound, _BoundReader)
            else bound
        )
        if isinstance(value, bytes):
            return bytes.decode(value, "utf-8")
        if isinstance(value, str):
            return str.__str__(value)
    except EsolangError as error:
        _remember_acquisition_failure(error)
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
