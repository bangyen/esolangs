"""Gzip text with streaming export and expanded-character measurements."""

from __future__ import annotations

import codecs
import gzip
import io
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from esolangs.exceptions import ArgumentError, ProgramError

if TYPE_CHECKING:
    from esolangs.settings import DialectSettings


@dataclass(frozen=True)
class CompressedText:
    """Validated UTF-8 gzip source; len counts expanded characters."""

    data: bytes
    language: str | None = None
    settings: DialectSettings | None = None
    _size: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate the stream and measure its expanded characters."""
        if not isinstance(self.data, bytes):
            raise ProgramError("gzip source must be bytes")
        object.__setattr__(self, "_size", sum(len(chunk) for chunk in self.chunks()))

    def chunks(self) -> Iterator[str]:
        """Yield decoded text in bounded chunks, validating gzip and UTF-8."""
        try:
            decoder = codecs.getincrementaldecoder("utf-8")()
            with gzip.GzipFile(fileobj=io.BytesIO(self.data)) as stream:
                while block := stream.read(65536):
                    yield decoder.decode(block)
                yield decoder.decode(b"", final=True)
        except (OSError, EOFError, UnicodeError, zlib.error) as error:
            raise ProgramError("invalid gzip UTF-8 source") from error

    @classmethod
    def from_chunks(cls, chunks: Iterable[str]) -> CompressedText:
        """Compress text deterministically without collecting expanded source."""
        output = io.BytesIO()
        with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as stream:
            for chunk in chunks:
                stream.write(chunk.encode("utf-8"))
        return cls(output.getvalue())

    @classmethod
    def repeated(cls, character: str, count: int) -> CompressedText:
        """Compress count copies of one character using bounded chunks."""
        if len(character) != 1 or type(count) is not int or count < 0:
            raise ArgumentError(
                "repeated source needs one character and a nonnegative count"
            )
        block = character * 65536
        return cls.from_chunks(
            block[: min(65536, count - start)] for start in range(0, count, 65536)
        )

    def __len__(self) -> int:
        """Return expanded characters."""
        return self._size

    def __str__(self) -> str:
        """Export ordinary source text."""
        return "".join(self.chunks())

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

        def chunks() -> Iterator[str]:
            column = 0
            for chunk in self.chunks():
                parts = []
                for start in range(0, len(chunk), 65536):
                    text = chunk[start : start + 65536]
                    offset = 0
                    while offset < len(text):
                        take = min(width - column, len(text) - offset)
                        parts.append(text[offset : offset + take])
                        offset += take
                        column += take
                        if column == width:
                            parts.append("\n")
                            column = 0
                yield "".join(parts)

        return self.from_chunks(chunks()).tagged(self.language, settings=self.settings)
