"""Gzip text with streaming export and expanded-character measurements."""

from __future__ import annotations

import codecs
import gzip
import io
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import KW_ONLY, dataclass, field
from inspect import getattr_static
from os import PathLike
from typing import ClassVar

from esolangs.exceptions import ArgumentError, GeneratorCapError, ProgramError
from esolangs.outcomes import _is_acquisition_failure, _track_acquisition_failures
from esolangs.runtime._files import (
    _STREAM_DEADLINE,
    StreamReadTimeoutError,
    _time_remaining,
    destination_path,
    write_staged,
)
from esolangs.runtime._validate import _argument_repr, _has_backing_type, check_width
from esolangs.runtime.memory import repr_value
from esolangs.runtime.source_hints import display_label, syntax_error


@dataclass(frozen=True, kw_only=True)
class TextLimits:
    """Independent raw-export, generation-work and compressed-file budgets."""

    plain_chars: int
    generation_chars: int
    gzip_bytes: int

    def __post_init__(self) -> None:
        """Require nonnegative integer budgets."""
        for name in ("plain_chars", "generation_chars", "gzip_bytes"):
            value = getattr(self, name)
            if type(value) is bool or not _has_backing_type(value, int):
                raise ArgumentError("text limits must be nonnegative integers")
            value = int.__int__(value)
            if value < 0:
                raise ArgumentError("text limits must be nonnegative integers")
            object.__setattr__(self, name, value)

    def __repr__(self) -> str:
        """Represent each budget even beyond the decimal digit cap."""
        return (
            f"{type(self).__qualname__}(plain_chars={repr_value(self.plain_chars)}, "
            f"generation_chars={repr_value(self.generation_chars)}, "
            f"gzip_bytes={repr_value(self.gzip_bytes)})"
        )


def _check_plain(limits: TextLimits, count: int) -> None:
    """Reject raw export before allocating or writing it."""
    if count > limits.plain_chars:
        raise GeneratorCapError(
            f"raw text exceeds the {_argument_repr(limits.plain_chars)}-character cap; "
            "use gzip"
        )


def _check_work(limits: TextLimits, count: int) -> None:
    """Reject expanded generation work before compression."""
    if count > limits.generation_chars:
        raise GeneratorCapError(
            f"generation exceeds the {_argument_repr(limits.generation_chars)}"
            "-character work cap"
        )


def _check_gzip(limits: TextLimits, count: int) -> None:
    """Reject a compressed file above its byte budget."""
    if count > limits.gzip_bytes:
        raise GeneratorCapError(
            f"gzip source exceeds the {_argument_repr(limits.gzip_bytes)}-byte file cap"
        )


#: Characters per gzip read and per repeated-source chunk.
_BLOCK = 65536
# An empty member still needs a 10-byte header, deflate end marker and trailer.
_MIN_GZIP_BYTES = 20


def _normalize_limits(limits: object) -> TextLimits | None:
    """Store only the validated budgets shared by native and portable gzip."""
    if limits is None or type(limits) is TextLimits:
        return limits
    if not _has_backing_type(limits, TextLimits):
        raise ArgumentError("limits must be a TextLimits or None")
    return TextLimits(
        plain_chars=limits.plain_chars,
        generation_chars=limits.generation_chars,
        gzip_bytes=limits.gzip_bytes,
    )


class _DeadlineGzipInput(io.BytesIO):
    """Check acquisition even when a gzip member yields no decoded bytes."""

    def __init__(self, data: bytes, deadline: float) -> None:
        super().__init__(data)
        self._deadline = deadline

    def read(self, size: int | None = -1, /) -> bytes:
        _time_remaining(self._deadline)
        # gzip can process many empty members or padding from a single pull.
        block = 8192
        return super().read(block if size is None or size < 0 else min(size, block))


@dataclass(frozen=True)
class CompressedText:
    """Validated UTF-8 gzip source; len counts expanded characters."""

    data: bytes
    _: KW_ONLY
    limits: TextLimits | None = None
    _size: int = field(init=False, repr=False)
    _has_newline: ClassVar[bool | None] = None
    _tail: ClassVar[str | None] = None

    def __post_init__(self) -> None:
        """Validate the stream and measure its expanded characters."""
        if not _has_backing_type(self.data, bytes):
            raise ProgramError("gzip source must be bytes")
        object.__setattr__(self, "data", bytes.__bytes__(self.data))
        limits = _normalize_limits(self.limits)
        object.__setattr__(self, "limits", limits)
        if limits is not None:
            _check_gzip(limits, len(self.data))
        size = 0
        has_newline = False
        tail = ""
        for chunk in CompressedText.chunks(self):
            size += len(chunk)
            has_newline = has_newline or "\n" in chunk
            tail = chunk[-1:] or tail
            if limits is not None:
                _check_work(limits, size)
        object.__setattr__(self, "_size", size)
        object.__setattr__(self, "_has_newline", has_newline)
        object.__setattr__(self, "_tail", tail)

    def chunks(self) -> Iterator[str]:
        """Yield decoded text in bounded chunks, validating gzip and UTF-8."""
        if not self.data:
            raise ProgramError("gzip source contains no gzip member")
        expanded_bytes = 0
        deadline = _STREAM_DEADLINE.get()
        try:
            decoder = codecs.getincrementaldecoder("utf-8")()
            source = (
                io.BytesIO(self.data)
                if deadline is None
                else _DeadlineGzipInput(self.data, deadline)
            )
            with gzip.GzipFile(fileobj=source) as stream:
                while True:
                    _time_remaining(deadline)
                    block = stream.read(_BLOCK)
                    _time_remaining(deadline)
                    if not block:
                        break
                    expanded_bytes += len(block)
                    yield decoder.decode(block)
                yield decoder.decode(b"", final=True)
        except StreamReadTimeoutError:
            raise
        except UnicodeDecodeError as error:
            # The decoder's input includes any partial UTF-8 sequence from the
            # preceding block, so its byte offsets are relative to that suffix.
            offset = expanded_bytes - len(error.object) + error.start
            raise syntax_error(
                f"invalid UTF-8 at decoded byte {offset} in gzip source",
                "save the text program as UTF-8 before compressing it",
                error_type=ProgramError,
            ) from error
        except EOFError as error:
            raise syntax_error(
                "truncated gzip source",
                "restore or re-export the complete gzip file",
                error_type=ProgramError,
            ) from error
        except (OSError, zlib.error) as error:
            raise syntax_error(
                f"invalid gzip source: {error}",
                "restore or re-export the program as a valid gzip file",
                error_type=ProgramError,
            ) from error

    @classmethod
    def from_chunks(
        cls, chunks: Iterable[str], *, limits: TextLimits | None = None
    ) -> CompressedText:
        """Compress text deterministically without collecting expanded source."""
        limits = _normalize_limits(limits)
        if not issubclass(type(chunks), Iterable):
            missing = object()
            if getattr_static(type(chunks), "__iter__", missing) is not missing:
                raise ArgumentError("chunks must be an iterable of strings")
            try:
                chunks = iter(chunks)
            except TypeError as error:
                raise ArgumentError("chunks must be an iterable of strings") from error
        if limits is not None:
            _check_gzip(limits, _MIN_GZIP_BYTES)
        output = io.BytesIO()
        count = 0
        has_newline = False
        tail = ""
        with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as stream:
            for text in chunks:
                if not _has_backing_type(text, str):
                    # ``[b"x"]`` raised AttributeError from ``.encode``.
                    raise ArgumentError(
                        f"chunks must be strings, got {type(text).__name__}"
                    )
                chunk = str.__str__(text)
                count += len(chunk)
                has_newline = has_newline or "\n" in chunk
                tail = chunk[-1:] or tail
                if limits is not None:
                    _check_work(limits, count)
                try:
                    encoded = chunk.encode("utf-8")
                except UnicodeEncodeError as error:
                    # A lone surrogate, which no source file can hold.
                    raise ArgumentError(
                        f"chunks must be valid UTF-8 text: {error}"
                    ) from error
                stream.write(encoded)
                if limits is not None:
                    _check_gzip(limits, output.tell())
        data = output.getvalue()
        if limits is not None:
            _check_gzip(limits, len(data))
        return cls._measured(data, count, limits, has_newline=has_newline, tail=tail)

    @classmethod
    def _measured(
        cls,
        data: bytes,
        size: int,
        limits: TextLimits | None,
        *,
        has_newline: bool | None,
        tail: str | None,
    ) -> CompressedText:
        """Build from a stream already known valid and ``size`` characters long.

        Skips __post_init__'s decompress-to-measure pass, which was most of
        Unary's generation time at nine inputs.
        """
        text = object.__new__(cls)
        object.__setattr__(text, "data", data)
        object.__setattr__(text, "limits", limits)
        object.__setattr__(text, "_size", size)
        object.__setattr__(text, "_has_newline", has_newline)
        object.__setattr__(text, "_tail", tail)
        return text

    def _is_multiline(self) -> bool:
        """Use the newline measured at creation, with a fallback for old pickles."""
        known = self._has_newline
        return (
            any("\n" in chunk for chunk in CompressedText.chunks(self))
            if known is None
            else known
        )

    def _last_character(self) -> str:
        """Return the decoded tail, inspecting old records only if needed."""
        tail = self._tail
        if tail is None:
            tail = ""
            for chunk in CompressedText.chunks(self):
                tail = chunk[-1:] or tail
        return tail

    def _inherit_limits(self, original: TextLimits | None) -> CompressedText:
        """Apply both versions' caps to the stored stream and measured length."""
        if original is None:
            return self
        limits = self.limits
        combined = (
            original
            if limits is None
            else TextLimits(
                plain_chars=min(limits.plain_chars, original.plain_chars),
                generation_chars=min(
                    limits.generation_chars, original.generation_chars
                ),
                gzip_bytes=min(limits.gzip_bytes, original.gzip_bytes),
            )
        )
        if combined == limits:
            return self
        _check_gzip(combined, len(self.data))
        _check_work(combined, self._size)
        return self._measured(
            self.data,
            self._size,
            combined,
            has_newline=self._has_newline,
            tail=self._tail,
        )

    @classmethod
    def repeated(
        cls, character: str, count: int, *, limits: TextLimits | None = None
    ) -> CompressedText:
        """Compress count copies of one character using bounded chunks."""
        limits = _normalize_limits(limits)
        if (
            not _has_backing_type(character, str)
            or str.__len__(character) != 1
            or type(count) is bool
            or not _has_backing_type(count, int)
        ):
            raise ArgumentError(
                "repeated source needs one character and a nonnegative count"
            )
        count = int.__int__(count)
        if count < 0:
            raise ArgumentError(
                "repeated source needs one character and a nonnegative count"
            )
        if limits is not None:
            _check_work(limits, count)
        block = str.__str__(character) * _BLOCK
        return cls.from_chunks(
            (block[: min(_BLOCK, count - start)] for start in range(0, count, _BLOCK)),
            limits=limits,
        )

    def __len__(self) -> int:
        """Return expanded characters."""
        return self._size

    def __str__(self) -> str:
        """Export ordinary source text."""
        return "".join(CompressedText.plain_chunks(self))

    def plain_chunks(self) -> Iterator[str]:
        """Enforce the raw-export budget before yielding any text."""
        if self.limits is not None:
            _check_plain(self.limits, self._size)
        return CompressedText.chunks(self)

    def to_gzip(self) -> bytes:
        """Return the compressed file bytes."""
        return self.data

    def to_file(self, path: str | PathLike[str]) -> None:
        """Write a gzip source file, replacing it only after writing succeeds.

        Raises:
            ProgramError: The file cannot be written.
        """
        with _track_acquisition_failures():
            try:
                target = destination_path(path)
            except (ArgumentError, OSError) as exc:
                if _is_acquisition_failure(exc):
                    raise
                raise ProgramError(f"cannot save program: {exc}") from exc
        try:
            write_staged(target, (self.data,))
        except (OSError, TypeError, ValueError) as exc:
            raise ProgramError(
                f"cannot save program to {display_label(target.spelling)}: {exc}"
            ) from exc

    def wrapped(self, width: int | None) -> CompressedText:
        """Insert line breaks at width without collecting expanded source.

        Return the original archive if no line breaks are needed.
        """
        width = check_width(width)
        return self if width is None else self._wrap_characters(width, terminal=True)

    def _wrap_characters(self, width: int, *, terminal: bool = False) -> CompressedText:
        """Fold characters and retain the archive when no breaks are inserted."""
        size = self._size
        breaks = (size if terminal else size - 1) // width
        if breaks <= 0:
            return self

        if self.limits is not None:
            _check_work(self.limits, size + breaks)

        def chunks() -> Iterator[str]:
            column = 0
            remaining = breaks
            # Each decoded chunk is at most one block, so it is wrapped whole.
            for chunk in CompressedText.chunks(self):
                parts = []
                offset = 0
                while offset < len(chunk):
                    take = min(width - column, len(chunk) - offset)
                    parts.append(chunk[offset : offset + take])
                    offset += take
                    column += take
                    if column == width:
                        if remaining:
                            parts.append("\n")
                            remaining -= 1
                        column = 0
                yield "".join(parts)

        return self.from_chunks(chunks(), limits=self.limits)


def _freeze_compressed(source: CompressedText) -> CompressedText:
    """Use a validated archive without inheriting subclass dispatch."""
    if type(source) is CompressedText:
        return source
    return CompressedText(source.data, limits=source.limits)
