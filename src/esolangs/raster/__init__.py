"""Shared immutable raster source for image-based languages."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from itertools import takewhile
from operator import is_not
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from esolangs.settings import DialectSettings

from esolangs.exceptions import MissingDependencyError, ProgramError
from esolangs.interpreters.source_hints import syntax_error

from . import png

Pixel = tuple[int, int, int]
Rows = tuple[tuple[Pixel, ...], ...]


def _freeze_rows(rows: Rows) -> Rows:
    """Return validated immutable RGB rows, detached from the caller."""
    # Generated images reuse immutable palette tuples millions of times.
    # Identity avoids equality accepting bool/float channels as cached integers.
    validated: dict[int, Pixel] = {}
    validated_rows: dict[int, tuple[Pixel, ...]] = {}
    frozen_rows = []
    for row in rows:
        if type(row) is tuple and id(row) in validated_rows:
            frozen_rows.append(validated_rows[id(row)])
            continue
        frozen_row: list[Pixel] | None = None if type(row) is tuple else []
        previous: Pixel | None = None
        for pixel in row:
            if previous is not None and pixel is previous:
                if frozen_row is not None:
                    frozen_row.append(pixel)
                continue
            if type(pixel) is tuple and id(pixel) in validated:
                if frozen_row is not None:
                    frozen_row.append(pixel)
                previous = pixel
                continue
            frozen = tuple(pixel)
            if len(frozen) != 3 or any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= 255
                for value in frozen
            ):
                raise syntax_error(
                    "Raster pixels must be 8-bit RGB triples",
                    (
                        "use three integer RGB channels from 0 through 255 for "
                        "every pixel"
                    ),
                )
            if frozen_row is None and frozen is not pixel:
                frozen_row = list(takewhile(partial(is_not, pixel), row))
            if frozen_row is not None:
                frozen_row.append(frozen)
            if type(pixel) is tuple:
                previous = pixel
                if len(validated) < 1024:
                    validated[id(pixel)] = pixel
            else:
                previous = None
        immutable_row = row if frozen_row is None else tuple(frozen_row)
        frozen_rows.append(immutable_row)
        if frozen_row is None and len(validated_rows) < 1024:
            validated_rows[id(row)] = immutable_row
    result = tuple(frozen_rows)
    width = len(result[0]) if result else 0
    if not result or not width or any(len(row) != width for row in result):
        raise syntax_error(
            "Raster needs non-empty equal-width rows",
            ("provide at least one nonempty row and keep all rows the same width"),
        )
    return result


@dataclass(frozen=True, init=False, eq=False)
class Raster:
    """An immutable 8-bit RGB image source, stored row by row."""

    _rows: Rows | None = field(default=None, repr=False)
    _normalizations: dict[int | None, Rows] = field(
        default_factory=dict, repr=False, compare=False
    )
    _materialize: Callable[[], Rows] | None = field(
        default=None, repr=False, compare=False
    )
    _payload: object | None = field(default=None, repr=False, compare=False)
    _language: str | None = field(default=None, repr=False, compare=False)
    _settings: DialectSettings | None = field(default=None, repr=False, compare=False)

    def __init__(
        self,
        rows: Rows | None = None,
        *,
        _materialize: Callable[[], Rows] | None = None,
        _payload: object | None = None,
        language: str | None = None,
        settings: DialectSettings | None = None,
    ) -> None:
        """Create a raster from pixels or a lazy language-owned renderer."""
        object.__setattr__(self, "_rows", rows)
        object.__setattr__(self, "_normalizations", {})
        object.__setattr__(self, "_materialize", _materialize)
        object.__setattr__(self, "_payload", _payload)
        object.__setattr__(self, "_language", language)
        object.__setattr__(self, "_settings", settings)
        self.__post_init__()

    def __post_init__(self) -> None:
        """Validate the rectangular raster shape."""
        if self._rows is None:
            if self._materialize is None:
                raise syntax_error(
                    "Raster needs pixels or a materializer",
                    "supply RGB pixels or a function that materializes them",
                )
            return
        object.__setattr__(self, "_rows", _freeze_rows(self._rows))

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

    @property
    def settings(self) -> DialectSettings | None:
        """The retained dialect choices, absent on decoded PNGs."""
        return self._settings

    def tagged(self, language: str, settings: DialectSettings | None = None) -> Raster:
        """Return this raster tagged as generated for ``language``."""
        return Raster(
            self._rows,
            _materialize=self._materialize,
            _payload=self._payload,
            language=language,
            settings=self.settings
            if settings is None and language == self.language
            else settings,
        )

    @property
    def rows(self) -> Rows:
        """Return RGB rows, materializing lazy source on first access."""
        if self._rows is None:
            materialize = cast("Callable[[], Rows]", self._materialize)
            object.__setattr__(self, "_rows", _freeze_rows(materialize()))
        return cast("Rows", self._rows)

    def _normalized(self, scale: int | None = None) -> Rows:
        """Return cached codel rows; explicit and detected scales stay distinct."""
        from esolangs._validate import check_scale

        from .scale import normalize

        if scale is not None:
            check_scale(scale)
        if scale not in self._normalizations:
            self._normalizations[scale] = normalize(self.rows, scale)
        return self._normalizations[scale]

    def upscaled(self, scale: int = 1) -> Raster:
        """Replicate pixels into solid squares, preserving language ownership."""
        from esolangs._validate import check_scale

        check_scale(scale)
        if scale == 1:
            return self

        def materialize() -> Rows:
            rows = [
                tuple(pixel for pixel in row for _ in range(scale)) for row in self.rows
            ]
            return tuple(row for row in rows for _ in range(scale))

        return Raster(
            _materialize=materialize,
            _payload=self._payload,
            language=self.language,
            settings=self.settings,
        )

    @classmethod
    def from_png(cls, data: bytes) -> Raster:
        """Decode PNG bytes into raster source.

        Untrusted bytes: a corrupt chunk used to escape as a bare
        ``zlib.error``/``struct.error``/``IndexError``/``MemoryError``.
        Any decode failure is a bad program, so it becomes a
        :class:`~esolangs.exceptions.ProgramError`.
        """
        try:
            decoded = png._rgb_rows(data)  # noqa: SLF001
            # Inside the guard too: a 0x0 image decodes cleanly and then
            # ``__post_init__`` rejects the empty rows, which is still a bad
            # PNG rather than a caller error.
            return cls(decoded)
        except MissingDependencyError:
            raise
        except Exception as exc:
            error = ProgramError(f"not a readable PNG: {exc}")
            for note in getattr(exc, "__notes__", ()):
                error.add_note(note)
            if not getattr(error, "__notes__", ()):
                error.add_note("hint: restore or re-export the drawing as a valid PNG")
            raise error from exc

    def to_png(self) -> bytes:
        """Encode this raster as PNG bytes."""
        return png.write_rgb(self.rows)
