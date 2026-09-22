"""Shared immutable raster source for image-based languages."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from esolangs.exceptions import ProgramError

from . import png

Pixel = tuple[int, int, int]
Rows = tuple[tuple[Pixel, ...], ...]


@dataclass(frozen=True, init=False, eq=False)
class Raster:
    """An immutable 8-bit RGB image source, stored row by row."""

    _rows: Rows | None = field(default=None, repr=False)
    _materialize: Callable[[], Rows] | None = field(
        default=None, repr=False, compare=False
    )
    _payload: object | None = field(default=None, repr=False, compare=False)
    _language: str | None = field(default=None, repr=False, compare=False)

    def __init__(
        self,
        rows: Rows | None = None,
        *,
        _materialize: Callable[[], Rows] | None = None,
        _payload: object | None = None,
        language: str | None = None,
    ) -> None:
        """Create a raster from pixels or a lazy language-owned renderer."""
        object.__setattr__(self, "_rows", rows)
        object.__setattr__(self, "_materialize", _materialize)
        object.__setattr__(self, "_payload", _payload)
        object.__setattr__(self, "_language", language)
        self.__post_init__()

    def __post_init__(self) -> None:
        """Validate the rectangular raster shape."""
        if self._rows is None:
            if self._materialize is None:
                raise ValueError("Raster needs pixels or a materializer")
            return
        width = len(self._rows[0]) if self._rows else 0
        valid = all(
            len(pixel) == 3 and all(0 <= value <= 255 for value in pixel)
            for row in self._rows
            for pixel in row
        )
        if not self._rows or not width or any(len(row) != width for row in self._rows):
            raise ValueError("Raster needs non-empty equal-width rows")
        if not valid:
            raise ValueError("Raster pixels must be 8-bit RGB triples")

    def __eq__(self, other: object) -> bool:
        """Whether two rasters have identical RGB pixels."""
        return isinstance(other, Raster) and self.rows == other.rows

    def __hash__(self) -> int:
        """Hash the immutable RGB pixels."""
        return hash(self.rows)

    @property
    def language(self) -> str | None:
        """The language :func:`esolangs.generate` tagged this for, if any.

        A PNG read back from disk carries no tag, exactly as a text program
        written to a file stops being a ``_Tagged``.  ``check_program`` reads
        this to refuse a cross-language run, which text programs already do.
        """
        return self._language

    def tagged(self, language: str) -> Raster:
        """Return this raster tagged as generated for ``language``."""
        return Raster(
            self._rows,
            _materialize=self._materialize,
            _payload=self._payload,
            language=language,
        )

    @property
    def rows(self) -> Rows:
        """Return RGB rows, materializing lazy source on first access."""
        if self._rows is None:
            materialize = cast("Callable[[], Rows]", self._materialize)
            object.__setattr__(self, "_rows", materialize())
        return cast("Rows", self._rows)

    @classmethod
    def from_png(cls, data: bytes) -> Raster:
        """Decode PNG bytes into raster source.

        Untrusted bytes: a corrupt chunk used to escape as a bare
        ``zlib.error``/``struct.error``/``IndexError``/``MemoryError``.
        Any decode failure is a bad program, so it becomes a
        :class:`~esolangs.exceptions.ProgramError`.
        """
        try:
            decoded = png.read_rgb(data)
            # Inside the guard too: a 0x0 image decodes cleanly and then
            # ``__post_init__`` rejects the empty rows, which is still a bad
            # PNG rather than a caller error.
            return cls(tuple(tuple(row) for row in decoded))
        except Exception as exc:
            raise ProgramError(f"not a readable PNG: {exc}") from exc

    def to_png(self) -> bytes:
        """Encode this raster as PNG bytes."""
        return png.write_rgb([list(row) for row in self.rows])
