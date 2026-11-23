"""Input containers normalized without imposing a language input unit."""

from __future__ import annotations

from codecs import getincrementaldecoder
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
from esolangs.runtime._files import decode_utf8, read_snapshot
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.source_hints import with_hint

#: A stream is consumed from its current position.  Spelled with ``typing.IO``
#: so the public alias names no private type; at runtime any ``.read()`` does.
type InputSource = str | bytes | IO[str] | IO[bytes]


@dataclass(frozen=True, slots=True)
class InputFrame:
    """A Boolean record's length in characters or LF-delimited lines."""

    units: int
    lines: bool

    def prefix(self, text: str) -> str:
        """Keep one record and its line terminators."""
        if not self.lines:
            return text[: self.units]
        end = 0
        for _ in range(self.units):
            end = text.find("\n", end) + 1
            if end == 0:
                return text
        return text[:end]

    def read(self, bound: _BoundReader) -> str:
        """Read up to the record boundary without taking a byte from its tail."""
        return self.read_units(
            lambda: read_snapshot(bound.stream, reader=bound.read, size=1)
        )

    def read_units(
        self, read: Callable[[], str | bytes], *, encoding: str = "utf-8"
    ) -> str:
        """Read single units through the frame using the caller's transport."""
        decoder = getincrementaldecoder(encoding)()
        remaining = self.units
        parts: list[str] = []
        binary = False
        consumed = 0
        while remaining:
            value = read()
            if _has_backing_type(value, str):
                if binary:
                    raise TypeError("stdin stream changed from bytes to text")
                char = str.__str__(value)
            elif _has_backing_type(value, bytes):
                binary = True
                data = bytes.__bytes__(value)
                consumed += len(data)
                try:
                    char = decoder.decode(data, final=not data)
                    if not data:
                        # utf-8-sig can leave an incomplete BOM buffered at EOF.
                        pending, _ = decoder.getstate()
                        if pending:
                            char += pending.decode(encoding)
                except UnicodeDecodeError as error:
                    # The decoder includes any buffered prefix in its error.
                    raise input_read_error(
                        error, byte_offset=consumed - len(error.object)
                    ) from error
                if data and not char:
                    continue
            else:
                raise TypeError("stdin stream must return a string or bytes")
            if not char:
                break
            if len(char) != 1:
                raise ValueError("stdin stream returned too much input for read(1)")
            parts.append(char)
            if not self.lines or char == "\n":
                remaining -= 1
        return "".join(parts)


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


def _bind_input_reader(stream: IO[str] | IO[bytes]) -> _BoundReader | None:
    """Bind a stream's callable reader without consuming input."""
    try:
        reader = getattr(stream, "read", None)
        _preflight_standard_reader(stream, reader)
    except EsolangError as error:
        _remember_acquisition_failure(error)
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise input_read_error(exc) from exc
    return _BoundReader(stream, reader) if callable(reader) else None


def _unreadable_input(source: object) -> ArgumentError:
    return with_hint(
        ArgumentError(
            "stdin must be a string, bytes, or a readable stream, got "
            f"{type(source).__name__}"
        ),
        ("to read a file, pass its open stream or its UTF-8 text contents"),
    )


def check_input(source: InputSource) -> CheckedInput:
    """Validate literal stdin or bind a reader without consuming its stream."""
    if _has_backing_type(source, str):
        return str.__str__(source)
    if _has_backing_type(source, bytes):
        return _decode_input(source)
    checked = _bind_input_reader(cast("IO[str] | IO[bytes]", source))
    if checked is None:
        raise _unreadable_input(source)
    return checked


def input_read_error(detail: Exception | str, *, byte_offset: int = 0) -> ArgumentError:
    """Build a stdin error with the repair shared by Python and the CLI."""
    if isinstance(detail, UnicodeDecodeError):
        offset = byte_offset + detail.start
        detail = f"not text (invalid {detail.encoding.upper()} at byte {offset})"
    return with_hint(
        ArgumentError(f"cannot read stdin: {detail}"),
        ("open the input stream for reading and encode binary input as UTF-8"),
    )


def _decode_input(value: bytes) -> str:
    try:
        return decode_utf8(value)
    except UnicodeDecodeError as exc:
        raise input_read_error(exc) from exc


def read_input(
    source: InputSource | CheckedInput, *, frame: InputFrame | None = None
) -> str:
    """Snapshot input through the selected record boundary or physical EOF."""
    bound = (
        source
        if _has_backing_type(source, _BoundReader)
        else check_input(cast("InputSource", source))
    )
    if isinstance(bound, str):
        return bound if frame is None else frame.prefix(bound)
    try:
        if frame is not None:
            return frame.read(bound)
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
