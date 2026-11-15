"""Input containers normalized without imposing a language input unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from inspect import getattr_static
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
from types import BuiltinMethodType, GetSetDescriptorType
from typing import IO, cast

from esolangs.exceptions import ArgumentError, EsolangError
from esolangs.outcomes import _remember_acquisition_failure
from esolangs.runtime._files import read_snapshot
from esolangs.runtime._validate import _has_backing_type
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


def _preflight_standard_reader(stream: IO[str] | IO[bytes], reader: object) -> None:
    """Check native stream mode without probing user-defined reader methods."""
    if (
        not _has_backing_type(reader, BuiltinMethodType)
        or reader.__self__ is not stream
        or reader.__name__ != "read"
    ):
        return
    for kind in _STANDARD_STREAMS:
        if not issubclass(type(stream), kind):
            continue
        if getattr_static(stream, "read") is not kind.read:
            continue
        closed = cast("GetSetDescriptorType", kind.closed).__get__(stream)
        if closed or not kind.readable(cast(IOBase, stream)):
            # The native reader supplies the precise error without consuming input.
            reader(0)
        return


def check_input(source: InputSource) -> CheckedInput:
    """Validate literal stdin or bind a reader without consuming its stream."""
    if _has_backing_type(source, str):
        return str.__str__(source)
    if _has_backing_type(source, bytes):
        return _decode_input(source)
    stream = cast("IO[str] | IO[bytes]", source)
    try:
        reader = getattr(stream, "read", None)
        _preflight_standard_reader(stream, reader)
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
    return _BoundReader(stream, reader)


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
    bound = (
        source
        if _has_backing_type(source, _BoundReader)
        else check_input(cast("InputSource", source))
    )
    if isinstance(bound, str):
        return bound
    try:
        value = read_snapshot(bound.stream, reader=bound.read)
    except EsolangError as error:
        _remember_acquisition_failure(error)
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise input_read_error(exc) from exc
    if _has_backing_type(value, bytes):
        return _decode_input(value)
    if _has_backing_type(value, str):
        return str.__str__(value)
    raise with_hint(
        ArgumentError("stdin stream must return a string or bytes"),
        (
            "make stream.read() return text or UTF-8 "
            "bytes; alternatively pass the contents "
            "directly"
        ),
    )
