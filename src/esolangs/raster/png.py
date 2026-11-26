"""PNG I/O through the optional image extra; alpha is discarded."""

from __future__ import annotations

import io
import re
from collections.abc import Buffer, Sequence
from contextlib import ExitStack
from os import fsdecode, fsencode, fspath
from typing import TYPE_CHECKING, Any, cast

from esolangs._dialect import DialectSettings
from esolangs.exceptions import (
    EsolangError,
    MissingDependencyError,
    ProgramError,
)
from esolangs.raster._png_chunks import _backing_bytes
from esolangs.raster._png_metadata import (
    SourceMetadataSizeError as SourceMetadataSizeError,
)
from esolangs.raster._png_metadata import (
    _attach_metadata,
    _source_claims,
)
from esolangs.raster._png_metadata import (
    attach_source_metadata as attach_source_metadata,
)
from esolangs.raster._png_metadata import (
    check_source_fields as check_source_fields,
)
from esolangs.raster._png_metadata import (
    read_metadata as read_metadata,
)
from esolangs.raster._png_metadata import (
    write_metadata as write_metadata,
)
from esolangs.raster._png_validation import (
    _GREY,
    _PALETTE,
    _check_pixel_limit,
    _validate_png,
)
from esolangs.runtime._files import _STREAM_DEADLINE, _time_remaining
from esolangs.runtime._validate import (
    _argument_repr,
    _has_backing_type,
)
from esolangs.runtime.source_hints import (
    syntax_error,
)

if TYPE_CHECKING:
    from esolangs.raster import Pixel, Raster, Rows
    from esolangs.registry._catalog import Catalog

_UNLOADED = object()
Image: Any = _UNLOADED


def _require_image() -> Any:
    """Return Pillow or name the extra that installs it."""
    global Image  # noqa: PLW0603 - the module global is the lazy-import cache: Pillow is an optional extra, imported once on first use
    if Image is _UNLOADED:
        # Text-only workers paid 29 ms importing Pillow before using PNG I/O.
        try:
            from PIL import Image as PillowImage
        except ModuleNotFoundError:
            Image = None
        else:
            Image = PillowImage
    if Image is None:
        raise MissingDependencyError(
            "PNG I/O requires optional image support; "
            "install it with `pip install 'esolangs[image]'`"
        )
    return Image


def _read(data: Buffer, mode: str) -> tuple[bytes, int]:
    deadline = _STREAM_DEADLINE.get()
    _time_remaining(deadline)
    data = _backing_bytes(data)
    _time_remaining(deadline)
    image = _require_image()
    width, depth, colour, palette = _validate_png(data, image.MAX_IMAGE_PIXELS)
    _time_remaining(deadline)
    with image.open(io.BytesIO(data), formats=["PNG"]) as opened:
        _time_remaining(deadline)
        opened.load()
        _time_remaining(deadline)
        if colour == _PALETTE and max(opened.tobytes()) >= len(palette) // 3:
            raise syntax_error(
                "palette index outside PLTE chunk",
                ("re-export the PNG so every palette index has a corresponding colour"),
            )
        _time_remaining(deadline)
        if colour == _GREY and depth == 16:
            # I;16 -> L clips; taking the high byte preserves dark strokes.
            raw = opened.tobytes("raw", "I;16B")
            _time_remaining(deadline)
            with image.frombytes("L", opened.size, raw[0::2]) as grey:
                raw = grey.convert(mode).tobytes()
        else:
            raw = opened.convert(mode).tobytes()
    _time_remaining(deadline)
    return raw, width


def read_grey(data: Buffer) -> list[bytearray]:
    """Decode PNG bytes to rows of greyscale levels, ignoring alpha."""
    raw, width = _read(data, "L")
    return [bytearray(raw[i : i + width]) for i in range(0, len(raw), width)]


_RGB_RUN = re.compile(rb"(.{3})\1*", re.DOTALL)


def _rgb_rows(data: Buffer) -> Rows:
    """Decode immutable RGB rows, reusing up to 1024 pixels and row patterns."""
    deadline = _STREAM_DEADLINE.get()
    raw, width = _read(data, "RGB")
    palette: dict[bytes, Pixel] = {}
    patterns: dict[bytes, tuple[Pixel, ...]] = {}
    rows = []
    stride = width * 3
    for offset in range(0, len(raw), stride):
        if deadline is not None:
            _time_remaining(deadline)
        scanline = raw[offset : offset + stride]
        row = patterns.get(scanline)
        if row is None:
            pixels = []
            for run in _RGB_RUN.finditer(scanline):
                key = run[1]
                pixel = palette.get(key)
                if pixel is None:
                    if len(palette) == 1024:
                        _time_remaining(deadline)
                        pixels = list(zip(raw[0::3], raw[1::3], raw[2::3], strict=True))
                        _time_remaining(deadline)
                        decoded = tuple(
                            tuple(pixels[i : i + width])
                            for i in range(0, len(pixels), width)
                        )
                        _time_remaining(deadline)
                        return decoded
                    pixel = (key[0], key[1], key[2])
                    palette[key] = pixel
                pixels.extend([pixel] * ((run.end() - run.start()) // 3))
            row = tuple(pixels)
            if len(patterns) < 1024:
                patterns[scanline] = row
        rows.append(row)
    _time_remaining(deadline)
    return tuple(rows)


def read_rgb(data: Buffer) -> list[list[tuple[int, int, int]]]:
    """Decode PNG bytes to independent mutable RGB rows, ignoring alpha."""
    return [list(row) for row in _rgb_rows(data)]


def _write(image: Any, mode: str, width: int, height: int, raw: bytes) -> bytes:
    output = io.BytesIO()
    with image.frombytes(mode, (width, height), raw) as opened:
        opened.save(output, format="PNG")
    return output.getvalue()


def _grey_rows(
    pixels: Sequence[Buffer], buffers: ExitStack
) -> tuple[int, list[bytes | bytearray | memoryview]] | None:
    """Bind rectangular rows, acquiring each generic buffer at most once."""
    seen: dict[int, tuple[Buffer, memoryview]] = {}
    rows: list[bytes | bytearray | memoryview] = []
    width = 0
    for row in pixels:
        if _has_backing_type(row, bytearray):
            samples: bytes | bytearray | memoryview = row
            size = bytearray.__len__(row)
        elif _has_backing_type(row, bytes):
            samples = row
            size = bytes.__len__(row)
        else:
            bound = seen.get(id(row))
            if bound is None:
                bound = row, buffers.enter_context(memoryview(row))
                seen[id(row)] = bound
            samples = bound[1]
            size = samples.nbytes
        if size == 0 or (width and size != width):
            return None
        width = size
        rows.append(samples)
    return (width, rows) if rows else None


def _pack_grey_rows(rows: list[bytes | bytearray | memoryview], width: int) -> bytes:
    """Recheck widths after callbacks, pinning mutable rows until packed."""
    parts: list[bytes | memoryview] = []
    pinned: list[memoryview] = []
    try:
        for row in rows:
            if type(row) is bytearray:
                view = memoryview(row)
                pinned.append(view)
                part: bytes | memoryview = view
            elif type(row) is memoryview:
                part = row
            else:
                part = _backing_bytes(row)
            size = part.nbytes if type(part) is memoryview else len(part)
            if size != width:
                raise syntax_error(
                    "greyscale row width changed while encoding",
                    "provide nonempty, equal-width rows of greyscale pixels",
                )
            parts.append(part)
        return b"".join(parts)
    finally:
        for view in pinned:
            view.release()


def write_grey(pixels: list[bytearray]) -> bytes:
    """Encode rectangular greyscale rows as PNG bytes."""
    if type(pixels) is not list and _has_backing_type(pixels, list):
        pixels = list(list.__iter__(pixels))
    with ExitStack() as buffers:
        bound = _grey_rows(pixels, buffers)
        if bound is None:
            raise syntax_error(
                "expected a non-empty 2-D greyscale image with equal-length rows",
                "provide nonempty, equal-width rows of greyscale pixels",
            )
        width, rows = bound
        height = len(rows)
        image = _require_image()
        _check_pixel_limit(width, height, image.MAX_IMAGE_PIXELS)
        raw = _pack_grey_rows(rows, width)
    return _write(image, "L", width, height, raw)


def write_grey_file(path: str, pixels: list[bytearray]) -> None:
    """Write greyscale rows to ``path`` as a PNG."""
    from esolangs.runtime._files import _path_directory

    directory = _path_directory(path)
    data = write_grey(pixels)
    filename: str | bytes | int = path if _has_backing_type(path, int) else fspath(path)
    if _has_backing_type(filename, str):
        filename = str.__str__(filename)
    elif _has_backing_type(filename, bytes):
        filename = bytes.__bytes__(filename)
    target = filename
    if directory is not None and filename:
        if type(filename) is str:
            target = directory.resolve(filename)
        elif type(filename) is bytes:
            target = fsencode(directory.resolve(fsdecode(filename)))
    try:
        with open(target, "wb") as handle:
            handle.write(data)
    except OSError as error:
        if target != filename and error.filename == target:
            error.filename = filename
        raise


def _row_width(row: Sequence[Pixel]) -> int:
    """Measure tuple storage even if a subclass overrides its length."""
    return tuple.__len__(row) if _has_backing_type(row, tuple) else len(row)


def write_rgb(pixels: Sequence[Sequence[tuple[int, int, int]]]) -> bytes:
    """Encode rectangular 8-bit RGB rows as PNG bytes."""
    from esolangs.raster import _freeze_pixel

    if type(pixels) is not tuple and _has_backing_type(pixels, tuple):
        pixels = tuple(tuple.__iter__(pixels))
    shape_hint = "provide nonempty, equal-width rows of RGB pixels"
    try:
        height = len(pixels)
        width = _row_width(pixels[0]) if height else 0
        rectangular = bool(height and width) and all(
            _row_width(row) == width for row in pixels
        )
    except EsolangError:
        raise
    except (TypeError, ValueError, IndexError) as error:
        raise syntax_error(
            "expected a non-empty 2-D RGB image", shape_hint, error_type=ProgramError
        ) from error
    if not rectangular:
        raise syntax_error(
            "expected a non-empty 2-D RGB image",
            shape_hint,
        )
    image = _require_image()
    _check_pixel_limit(width, height, image.MAX_IMAGE_PIXELS)
    packed_rows: dict[int, tuple[Sequence[tuple[int, int, int]], bytes]] = {}
    packed_pixels: dict[int, tuple[tuple[int, int, int], bytes]] = {}
    cache_pixels = True
    parts = []
    row_bytes = width * 3
    for row in pixels:
        cached = packed_rows.get(id(row))
        if cached is not None:
            parts.append(cached[1])
            continue
        immutable = type(row) is tuple
        raw = bytearray()
        previous: tuple[int, int, int] | None = None
        previous_bytes = b""
        repeats = 0
        row_pixels = (
            tuple.__iter__(row)
            if not immutable and _has_backing_type(row, tuple)
            else row
        )
        for pixel in row_pixels:
            if previous is not None and pixel is previous:
                repeats += 1
                continue
            if repeats:
                raw.extend(previous_bytes * repeats)
                repeats = 0
            previous = None
            if cache_pixels:
                cached_pixel = packed_pixels.get(id(pixel))
                if cached_pixel is not None:
                    previous, previous_bytes = cached_pixel
                    repeats = 1
                    continue
            try:
                frozen = _freeze_pixel(pixel)
            except (ProgramError, TypeError) as error:
                raise syntax_error(
                    f"invalid RGB pixel {_argument_repr(pixel)}",
                    "use three integer RGB channels from 0 through 255",
                    error_type=ProgramError,
                ) from error
            raw.extend(frozen)
            if frozen is pixel:
                if cache_pixels:
                    previous = pixel
                    previous_bytes = bytes(frozen)
                    packed_pixels[id(pixel)] = pixel, previous_bytes
                    cache_pixels = len(packed_pixels) < 1024
            else:
                immutable = False
        if repeats:
            raw.extend(previous_bytes * repeats)
        if len(raw) != row_bytes:
            raise syntax_error("RGB row width changed while encoding", shape_hint)
        packed = bytes(raw)
        parts.append(packed)
        if immutable and len(packed_rows) < 1024:
            packed_rows[id(row)] = row, packed
    if len(parts) != height:
        raise syntax_error("RGB row count changed while encoding", shape_hint)
    return _write(image, "RGB", width, height, b"".join(parts))


def _write_grey_rgb(rows: tuple[bytes, ...]) -> bytes:
    """Encode greyscale levels with the same RGB PNG mode as ordinary rasters."""
    image = _require_image()
    size = len(rows[0]), len(rows)
    _check_pixel_limit(*size, image.MAX_IMAGE_PIXELS)
    output = io.BytesIO()
    with image.frombytes("L", size, b"".join(rows)) as grey, grey.convert("RGB") as rgb:
        rgb.save(output, format="PNG")
    return output.getvalue()


def write_source(
    pixels: Rows | Raster,
    language: str | None,
    settings: DialectSettings | None,
    scale: int | None,
    *,
    input_arity: int | None = None,
    catalog: Catalog | None = None,
) -> bytes:
    """Encode pixels and explicit native source metadata without retagging."""
    from esolangs.raster import Raster

    try:
        claims = _source_claims(
            language, settings, scale, input_arity=input_arity, catalog=catalog
        )
        image = (
            Raster.to_png(pixels)
            if _has_backing_type(pixels, Raster)
            else write_rgb(cast("Rows", pixels))
        )
        return (
            image
            if claims is None
            else _attach_metadata(image, claims, catalog=catalog)
        )
    except SourceMetadataSizeError as error:
        raise ProgramError(str(error)) from error
