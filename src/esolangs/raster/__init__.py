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

from esolangs.exceptions import ArgumentError, MissingDependencyError, ProgramError
from esolangs.runtime._validate import check_provenance, check_scale
from esolangs.runtime.source_hints import syntax_error

from . import png

Pixel = tuple[int, int, int]
Rows = tuple[tuple[Pixel, ...], ...]
#: An upscaled image renders at most this many pixels (8 bytes of row
#: reference each, 2 GiB).  ``generate("Piet", "0110", scale=99999)`` was
#: OOM-killed with no message; Line's n=10 program is 74M pixels at scale 1.
MAX_UPSCALED_PIXELS = 1 << 28


def _pixel_error() -> ValueError:
    """Return the ProgramError for a pixel that is not an 8-bit RGB triple."""
    return syntax_error(
        "Raster pixels must be 8-bit RGB triples",
        "use three integer RGB channels from 0 through 255 for every pixel",
        error_type=ProgramError,
    )


def _freeze_rows(rows: Rows) -> Rows:
    """Return validated immutable RGB rows, detached from the caller.

    Every refusal is a ProgramError: a raw ValueError or TypeError
    (``Raster(5)``) escaped ``except EsolangError``.
    """
    try:
        return _freeze_iterable_rows(rows)
    except TypeError as exc:
        raise _pixel_error() from exc


def _freeze_iterable_rows(rows: Rows) -> Rows:
    """:func:`_freeze_rows`, raising TypeError on a non-iterable row or pixel."""
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
                raise _pixel_error()
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
            error_type=ProgramError,
        )
    return result


def _assign(
    raster: Raster,
    rows: Rows | None,
    materialize: Callable[[], Rows] | None,
    payload: object | None,
    language: str | None,
    settings: DialectSettings | None,
    scale: int | None = None,
) -> Raster:
    """Initialize ``raster``'s fields; the one path both constructors share."""
    if scale is not None:
        check_scale(scale)
    language = check_provenance(language, settings)
    object.__setattr__(raster, "_rows", rows)
    object.__setattr__(raster, "_normalizations", {})
    object.__setattr__(raster, "_materialize", materialize)
    object.__setattr__(raster, "_payload", payload)
    object.__setattr__(raster, "_language", language)
    object.__setattr__(raster, "_settings", settings)
    object.__setattr__(raster, "_scale", scale)
    object.__setattr__(raster, "_hash", None)
    raster.__post_init__()
    return raster


def _rebuilt(
    rows: Rows,
    language: str | None,
    settings: DialectSettings | None,
    scale: int | None,
) -> Raster:
    """Unpickle a :class:`Raster` (``__reduce__``'s constructor)."""
    return Raster(rows, language=language, settings=settings, scale=scale)


def lazy_raster(
    materialize: Callable[[], Rows],
    payload: object | None = None,
    *,
    language: str | None = None,
    settings: DialectSettings | None = None,
    scale: int | None = None,
) -> Raster:
    """Return a raster whose pixels a language-owned renderer supplies.

    Not a ``Raster`` constructor argument, so the public signature names
    no renderer internals.
    """
    return _assign(
        Raster.__new__(Raster), None, materialize, payload, language, settings, scale
    )


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
    _scale: int | None = field(default=None, repr=False, compare=False)
    # Tuples cache no hash before 3.14; an lru_cache key rehashes every pixel.
    _hash: int | None = field(default=None, repr=False, compare=False)

    def __init__(
        self,
        rows: Rows,
        *,
        language: str | None = None,
        settings: DialectSettings | None = None,
        scale: int | None = None,
    ) -> None:
        """Create a raster from RGB pixel rows."""
        _assign(self, rows, None, None, language, settings, scale)

    def __post_init__(self) -> None:
        """Validate the rectangular raster shape."""
        if self._rows is None:
            if self._materialize is None:
                raise syntax_error(
                    "Raster needs pixels or a materializer",
                    "supply RGB pixels or a function that materializes them",
                    error_type=ProgramError,
                )
            return
        object.__setattr__(self, "_rows", _freeze_rows(self._rows))

    def __repr__(self) -> str:
        """Name the size, language and scale; a lazy raster stays unrendered."""
        size = (
            f"{len(self._rows[0])}x{len(self._rows)}"
            if self._rows is not None
            else "unrendered"
        )
        return f"Raster({size}, language={self.language!r}, scale={self.scale!r})"

    def __eq__(self, other: object) -> bool:
        """Whether two rasters have identical RGB pixels."""
        return isinstance(other, Raster) and self.rows == other.rows

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        """Pickle the pixels and tags: an upscaled raster's renderer is a closure."""
        return (_rebuilt, (self.rows, self.language, self.settings, self.scale))

    def __hash__(self) -> int:
        """Hash the immutable RGB pixels, once."""
        cached = self._hash
        if cached is None:
            cached = hash(self.rows)
            object.__setattr__(self, "_hash", cached)
        return cached

    @property
    def language(self) -> str | None:
        """The language retained by generated source or PNG metadata."""
        return self._language

    @property
    def settings(self) -> DialectSettings | None:
        """The retained dialect choices."""
        return self._settings

    @property
    def scale(self) -> int | None:
        """The retained pixel enlargement factor, absent on untagged images."""
        return self._scale

    def tagged(
        self,
        language: str,
        *,
        settings: DialectSettings | None = None,
        scale: int | None = None,
    ) -> Raster:
        """Return this raster tagged as generated for ``language``."""
        language = cast("str", check_provenance(language, None))
        return _assign(
            Raster.__new__(Raster),
            self._rows,
            self._materialize,
            self._payload,
            language,
            self.settings
            if settings is None and language == self.language
            else settings,
            self.scale if scale is None else scale,
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
        from .scale import normalize

        if scale is None:
            scale = self.scale
        if scale is not None:
            check_scale(scale)
        if scale not in self._normalizations:
            self._normalizations[scale] = normalize(self.rows, scale)
        return self._normalizations[scale]

    def upscaled(self, scale: int) -> Raster:
        """Replicate pixels into solid squares, preserving language ownership."""
        check_scale(scale)
        if scale == 1:
            return self

        def materialize() -> Rows:
            base = self.rows
            pixels = len(base) * len(base[0]) * scale * scale
            if pixels > MAX_UPSCALED_PIXELS:
                raise ArgumentError(
                    f"scale {scale} makes a {len(base[0]) * scale}x"
                    f"{len(base) * scale} image ({pixels} pixels), over the "
                    f"{MAX_UPSCALED_PIXELS}-pixel limit; use a smaller scale"
                )
            rows = [
                tuple(pixel for pixel in row for _ in range(scale)) for row in self.rows
            ]
            return tuple(row for row in rows for _ in range(scale))

        return lazy_raster(
            materialize,
            self._payload,
            language=self.language,
            settings=self.settings,
            scale=(self.scale or 1) * scale,
        )

    @classmethod
    def from_png(cls, data: bytes) -> Raster:
        """Decode PNG bytes into raster source.

        Untrusted bytes: a corrupt chunk used to escape as a bare
        ``zlib.error``/``struct.error``/``IndexError``/``MemoryError``.
        Any decode failure is a bad program, so it becomes a
        :class:`~esolangs.exceptions.ProgramError`; data that is not
        bytes-like is an :class:`~esolangs.exceptions.ArgumentError`.
        """
        if not isinstance(data, (bytes, bytearray, memoryview)):
            # ``None`` read "'NoneType' object is not subscriptable".
            raise ArgumentError(f"PNG data must be bytes, got {type(data).__name__}")
        data = bytes(data)
        try:
            decoded = png._rgb_rows(data)  # noqa: SLF001
            # Inside the guard too: a 0x0 image decodes cleanly and then
            # ``__post_init__`` rejects the empty rows, which is still a bad
            # PNG rather than a caller error.
            metadata = png.read_metadata(data)
            if metadata is None:
                return cls(decoded)
            from esolangs.registry import resolve
            from esolangs.settings import DialectSettings

            language = metadata.get("language")
            if language is not None:
                if not isinstance(language, str):
                    raise ValueError("PNG language must be a string")
                language = resolve(language)
            scale = metadata.get("scale")
            if scale is not None:
                check_scale(scale)
            # The JSON document's validation: ``{"integer": 5}`` once
            # surfaced as "int() can't convert non-string".
            from esolangs.portable import decode_settings

            settings = decode_settings(metadata.get("settings"))
            if settings is not None and language is not None:
                settings.options(language)
            return _assign(
                cls.__new__(cls), decoded, None, None, language, settings, scale
            )
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
        data = png.write_rgb(self.rows)
        if self.language is None and self.settings is None and self.scale is None:
            return data
        return png.write_metadata(
            data,
            {
                "version": 1,
                "language": self.language,
                "settings": None
                if self.settings is None
                else {
                    key: {"integer": hex(value)} if type(value) is int else value
                    for key, value in self.settings._items  # noqa: SLF001
                },
                "scale": self.scale,
            },
        )
