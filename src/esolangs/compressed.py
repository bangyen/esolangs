"""Gzip text with streaming export and expanded-character measurements."""

from __future__ import annotations

import codecs
import gzip
import io
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import KW_ONLY, dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from esolangs.exceptions import ArgumentError, GeneratorCapError, ProgramError
from esolangs.runtime._validate import check_provenance

if TYPE_CHECKING:
    from esolangs.settings import DialectSettings


@dataclass(frozen=True)
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

    def check_plain(self, count: int) -> None:
        """Reject raw export before allocating or writing it."""
        if count > self.plain_chars:
            raise GeneratorCapError(
                f"raw text exceeds the {self.plain_chars}-character cap; use gzip"
            )

    def check_work(self, count: int) -> None:
        """Reject expanded generation work before compression."""
        if count > self.generation_chars:
            raise GeneratorCapError(
                f"generation exceeds the {self.generation_chars}-character work cap"
            )

    def check_gzip(self, count: int) -> None:
        """Reject a compressed file above its byte budget."""
        if count > self.gzip_bytes:
            raise GeneratorCapError(
                f"gzip source exceeds the {self.gzip_bytes}-byte file cap"
            )


#: Characters per gzip read and per repeated-source chunk.
_BLOCK = 65536


def _check_limits(limits: object) -> None:
    """Refuse a ``limits`` that is not a TextLimits or None."""
    if limits is not None and not isinstance(limits, TextLimits):
        # ``limits=5`` raised a bare AttributeError from ``check_gzip``.
        raise ArgumentError("limits must be a TextLimits or None")


@dataclass(frozen=True)
class CompressedText:
    """Validated UTF-8 gzip source; len counts expanded characters."""

    data: bytes
    _: KW_ONLY
    language: str | None = None
    settings: DialectSettings | None = None
    limits: TextLimits | None = None
    _size: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate the stream and measure its expanded characters."""
        if not isinstance(self.data, bytes):
            raise ProgramError("gzip source must be bytes")
        # Canonical, so an alias tag compares equal to the name ``run`` checks.
        object.__setattr__(
            self, "language", check_provenance(self.language, self.settings)
        )
        _check_limits(self.limits)
        if self.limits is not None:
            self.limits.check_gzip(len(self.data))
        object.__setattr__(self, "_size", sum(len(chunk) for chunk in self.chunks()))
        if self.limits is not None:
            self.limits.check_work(self._size)

    def chunks(self) -> Iterator[str]:
        """Yield decoded text in bounded chunks, validating gzip and UTF-8."""
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
        _check_limits(limits)
        if not isinstance(chunks, Iterable):
            raise ArgumentError("chunks must be an iterable of strings")
        output = io.BytesIO()
        count = 0
        with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as stream:
            for chunk in chunks:
                if not isinstance(chunk, str):
                    # ``[b"x"]`` raised AttributeError from ``.encode``.
                    raise ArgumentError(
                        f"chunks must be strings, got {type(chunk).__name__}"
                    )
                count += len(chunk)
                if limits is not None:
                    limits.check_work(count)
                stream.write(chunk.encode("utf-8"))
                if limits is not None:
                    limits.check_gzip(output.tell())
        return cls(output.getvalue(), limits=limits)

    @classmethod
    def repeated(
        cls, character: str, count: int, *, limits: TextLimits | None = None
    ) -> CompressedText:
        """Compress count copies of one character using bounded chunks."""
        _check_limits(limits)
        if (
            not isinstance(character, str)
            or len(character) != 1
            or type(count) is not int
            or count < 0
        ):
            raise ArgumentError(
                "repeated source needs one character and a nonnegative count"
            )
        if limits is not None:
            limits.check_work(count)
        block = character * _BLOCK
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
            self.limits.check_plain(len(self))
        return self.chunks()

    def to_gzip(self) -> bytes:
        """Return the compressed file bytes."""
        return self.data

    def save(self, path: str | Path) -> None:
        """Write a gzip source file."""
        Path(path).write_bytes(self.data)

    def tagged(
        self, language: str | None, *, settings: DialectSettings | None = None
    ) -> CompressedText:
        """Retain generation provenance."""
        return replace(self, language=language, settings=settings)

    def wrapped(self, width: int | None) -> CompressedText:
        """Insert line breaks at width without collecting expanded source."""
        if width is None:
            return self
        if type(width) is not int or width < 1:
            raise ArgumentError("width must be a positive integer")

        if self.limits is not None:
            self.limits.check_work(len(self) + len(self) // width)

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

        return self.from_chunks(chunks(), limits=self.limits).tagged(
            self.language, settings=self.settings
        )
