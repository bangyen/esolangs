"""Gzip text with streaming export and expanded-character measurements."""

from __future__ import annotations

import codecs
import gzip
import io
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import KW_ONLY, dataclass, field
from os import PathLike
from typing import ClassVar

from esolangs.exceptions import ArgumentError, GeneratorCapError, ProgramError
from esolangs.runtime._files import explicit_path, write_staged
from esolangs.runtime._validate import _argument_repr, check_width
from esolangs.runtime.memory import repr_value


@dataclass(frozen=True, kw_only=True)
class TextLimits:
    """Independent raw-export, generation-work and compressed-file budgets."""

    plain_chars: int
    generation_chars: int
    gzip_bytes: int

    def __post_init__(self) -> None:
        """Require nonnegative integer budgets."""
        for value in (self.plain_chars, self.generation_chars, self.gzip_bytes):
            if type(value) is not int or value < 0:
                raise ArgumentError("text limits must be nonnegative integers")

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


def _normalize_limits(limits: object) -> TextLimits | None:
    """Store only the validated budgets shared by native and portable gzip."""
    if limits is None or type(limits) is TextLimits:
        return limits
    if not isinstance(limits, TextLimits):
        raise ArgumentError("limits must be a TextLimits or None")
    return TextLimits(
        plain_chars=limits.plain_chars,
        generation_chars=limits.generation_chars,
        gzip_bytes=limits.gzip_bytes,
    )


@dataclass(frozen=True)
class CompressedText:
    """Validated UTF-8 gzip source; len counts expanded characters."""

    data: bytes
    _: KW_ONLY
    limits: TextLimits | None = None
    _size: int = field(init=False, repr=False)
    _has_newline: ClassVar[bool | None] = None

    def __post_init__(self) -> None:
        """Validate the stream and measure its expanded characters."""
        if not isinstance(self.data, bytes):
            raise ProgramError("gzip source must be bytes")
        object.__setattr__(self, "data", bytes.__bytes__(self.data))
        limits = _normalize_limits(self.limits)
        object.__setattr__(self, "limits", limits)
        if limits is not None:
            _check_gzip(limits, len(self.data))
        size = 0
        has_newline = False
        for chunk in self.chunks():
            size += len(chunk)
            has_newline = has_newline or "\n" in chunk
            if limits is not None:
                _check_work(limits, size)
        object.__setattr__(self, "_size", size)
        object.__setattr__(self, "_has_newline", has_newline)

    def chunks(self) -> Iterator[str]:
        """Yield decoded text in bounded chunks, validating gzip and UTF-8."""
        if not self.data:
            raise ProgramError("gzip source contains no gzip member")
        try:
            decoder = codecs.getincrementaldecoder("utf-8")()
            with gzip.GzipFile(fileobj=io.BytesIO(self.data)) as stream:
                while block := stream.read(_BLOCK):
                    yield decoder.decode(block)
                yield decoder.decode(b"", final=True)
        except (OSError, EOFError, UnicodeError, zlib.error) as error:
            raise ProgramError("invalid gzip UTF-8 source") from error

    @classmethod
    def from_chunks(
        cls, chunks: Iterable[str], *, limits: TextLimits | None = None
    ) -> CompressedText:
        """Compress text deterministically without collecting expanded source."""
        limits = _normalize_limits(limits)
        if not isinstance(chunks, Iterable):
            raise ArgumentError("chunks must be an iterable of strings")
        output = io.BytesIO()
        count = 0
        has_newline = False
        with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as stream:
            for text in chunks:
                if not isinstance(text, str):
                    # ``[b"x"]`` raised AttributeError from ``.encode``.
                    raise ArgumentError(
                        f"chunks must be strings, got {type(text).__name__}"
                    )
                chunk = str.__str__(text)
                count += len(chunk)
                has_newline = has_newline or "\n" in chunk
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
        return cls._measured(data, count, limits, has_newline=has_newline)

    @classmethod
    def _measured(
        cls,
        data: bytes,
        size: int,
        limits: TextLimits | None,
        *,
        has_newline: bool | None,
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
        return text

    def _is_multiline(self) -> bool:
        """Use the newline measured at creation, with a fallback for old pickles."""
        known = self._has_newline
        return any("\n" in chunk for chunk in self.chunks()) if known is None else known

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
            self.data, self._size, combined, has_newline=self._has_newline
        )

    @classmethod
    def repeated(
        cls, character: str, count: int, *, limits: TextLimits | None = None
    ) -> CompressedText:
        """Compress count copies of one character using bounded chunks."""
        limits = _normalize_limits(limits)
        if (
            not isinstance(character, str)
            or str.__len__(character) != 1
            or type(count) is not int
            or count < 0
        ):
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
        return "".join(self.plain_chunks())

    def plain_chunks(self) -> Iterator[str]:
        """Enforce the raw-export budget before yielding any text."""
        if self.limits is not None:
            _check_plain(self.limits, len(self))
        return self.chunks()

    def to_gzip(self) -> bytes:
        """Return the compressed file bytes."""
        return self.data

    def to_file(self, path: str | PathLike[str]) -> None:
        """Write a gzip source file, replacing it only after writing succeeds.

        Raises:
            ProgramError: The file cannot be written.
        """
        try:
            target = explicit_path(path)
        except ArgumentError as exc:
            raise ProgramError(f"cannot save program: {exc}") from exc
        try:
            write_staged(target, (self.data,))
        except (OSError, TypeError, ValueError) as exc:
            raise ProgramError(f"cannot save program to {target}: {exc}") from exc

    def wrapped(self, width: int | None) -> CompressedText:
        """Insert line breaks at width without collecting expanded source."""
        width = check_width(width)
        if width is None:
            return self

        if self.limits is not None:
            _check_work(self.limits, len(self) + len(self) // width)

        def chunks() -> Iterator[str]:
            column = 0
            # Each decoded chunk is at most one block, so it is wrapped whole.
            for chunk in self.chunks():
                parts = []
                offset = 0
                while offset < len(chunk):
                    take = min(width - column, len(chunk) - offset)
                    parts.append(chunk[offset : offset + take])
                    offset += take
                    column += take
                    if column == width:
                        parts.append("\n")
                        column = 0
                yield "".join(parts)

        return self.from_chunks(chunks(), limits=self.limits)
