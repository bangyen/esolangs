"""Input containers normalized without imposing a language input unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from io import (
    BufferedRandom,
    BufferedReader,
    BufferedRWPair,
    BufferedWriter,
    BytesIO,
    FileIO,
    IOBase,
    StringIO,
    TextIOWrapper,
)
from types import BuiltinMethodType
from typing import IO, cast

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


type CheckedInput = str | _BoundReader

_STANDARD_STREAMS = (
    BufferedRandom,
    BufferedReader,
    BufferedRWPair,
    BufferedWriter,
    BytesIO,
    FileIO,
    StringIO,
    TextIOWrapper,
)


def check_input(source: InputSource) -> CheckedInput:
    """Validate literal stdin or bind a reader without consuming its stream."""
    if isinstance(source, str):
        return str.__str__(source)
    if isinstance(source, bytes):
        return _decode_input(source)
    try:
        reader = getattr(source, "read", None)
        kind = type(source)
        if (
            kind in _STANDARD_STREAMS
            and isinstance(reader, BuiltinMethodType)
            and reader.__self__ is source
            and (source.closed or not kind.readable(cast(IOBase, source)))
        ):
            # Let the standard reader supply its own error. A zero-size read
            # cannot consume input, even if one half of a stream pair is open.
            reader(0)
    except EsolangError as error:
        _remember_acquisition_failure(error)
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise input_read_error(exc) from exc
    if not callable(reader):
        raise with_hint(
            ArgumentError(
                "stdin must be a string, bytes, or a readable stream, got "
                f"{type(source).__name__}"
            ),
            ("to read a file, pass its open stream or its UTF-8 text contents"),
        )
    return _BoundReader(source, reader)


def input_read_error(detail: Exception | str) -> ArgumentError:
    """Build a stdin error with the repair shared by Python and the CLI."""
    return with_hint(
        ArgumentError(f"cannot read stdin: {detail}"),
        ("open the input stream for reading and encode binary input as UTF-8"),
    )


def _decode_input(value: bytes) -> str:
    try:
        return bytes.decode(value, "utf-8")
    except UnicodeDecodeError as exc:
        raise input_read_error(exc) from exc


def read_input(source: InputSource | CheckedInput) -> str:
    """Snapshot remaining input; binary input is UTF-8 text."""
    bound = source if isinstance(source, _BoundReader) else check_input(source)
    if isinstance(bound, str):
        return bound
    try:
        value = read_snapshot(bound.stream, reader=bound.read)
    except EsolangError as error:
        _remember_acquisition_failure(error)
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise input_read_error(exc) from exc
    if isinstance(value, bytes):
        return _decode_input(value)
    if isinstance(value, str):
        return str.__str__(value)
    raise with_hint(
        ArgumentError("stdin stream must return a string or bytes"),
        (
            "make stream.read() return text or UTF-8 "
            "bytes; alternatively pass the contents "
            "directly"
        ),
    )
