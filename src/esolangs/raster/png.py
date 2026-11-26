"""PNG I/O through the optional image extra; alpha is discarded."""

from __future__ import annotations

import io
import re
import struct
import sys
import zlib
from collections.abc import Buffer, Iterator, Sequence
from contextlib import ExitStack
from json import JSONDecoder
from json.encoder import encode_basestring_ascii
from os import fsdecode, fsencode, fspath
from typing import TYPE_CHECKING, Any

from esolangs._dialect import DialectSettings
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    MissingDependencyError,
    ProgramError,
)
from esolangs.outcomes import _is_acquisition_failure, _track_acquisition_failures
from esolangs.runtime._files import _STREAM_DEADLINE, _time_remaining
from esolangs.runtime._json import check_record_utf8, record_dumps, record_loads
from esolangs.runtime._validate import (
    _argument_repr,
    _has_backing_type,
    check_input_arity,
    check_scale,
)
from esolangs.runtime.source_hints import (
    display_label,
    program_error_context,
    syntax_error,
)

if TYPE_CHECKING:
    from esolangs.raster import Pixel, Rows
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


_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_REEXPORT = "restore or re-export the complete PNG image"
_IHDR = struct.Struct(">IIBBBBB")
_INFLATE_BLOCK = 65_536

# PNG colour type codes (IHDR byte 9).
_GREY = 0
_RGB = 2
_PALETTE = 3
_GREY_ALPHA = 4
_RGBA = 6

# Samples per pixel for each colour type.  Palette images store one index per
# pixel; the PLTE lookup turns that into colour later.
_CHANNELS = {_GREY: 1, _RGB: 3, _PALETTE: 1, _GREY_ALPHA: 2, _RGBA: 4}

_COLOUR_NAMES = {
    _GREY: "greyscale",
    _RGB: "truecolour",
    _PALETTE: "palette",
    _GREY_ALPHA: "greyscale+alpha",
    _RGBA: "truecolour+alpha",
}


def _backing_bytes(data: Buffer) -> bytes:
    """Snapshot an image buffer, bypassing overrides on bytes and bytearrays."""
    if type(data) is bytes:
        return data
    if _has_backing_type(data, bytes):
        return bytes.__bytes__(data)
    deadline = _STREAM_DEADLINE.get()
    _time_remaining(deadline)
    if _has_backing_type(data, bytearray):
        return bytes(bytearray.copy(data))
    try:
        with memoryview(data) as view:
            _time_remaining(deadline)
            return view.tobytes()
    except EsolangError:
        raise
    except TypeError as error:
        raise ArgumentError(
            f"PNG data must be bytes, got {type(data).__name__}"
        ) from error
    except (BufferError, ValueError) as error:
        raise ArgumentError(f"cannot read PNG data: {error}") from error


def _chunk_label(kind: bytes) -> str:
    """Render an untrusted chunk type for diagnostics."""
    return display_label(kind.decode("ascii", "replace"))


def _chunks(data: bytes) -> Iterator[tuple[bytes, bytes]]:
    """Yield validated chunks through the end of the PNG datastream."""
    deadline = _STREAM_DEADLINE.get()
    _time_remaining(deadline)
    if data[:8] != _SIGNATURE:
        raise syntax_error(
            "not a PNG file (bad signature)",
            "export the image as PNG instead of renaming another image format",
        )
    pos = 8
    while pos + 8 <= len(data):
        _time_remaining(deadline)
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if len(body) != length:
            raise syntax_error(
                f"truncated {_chunk_label(kind)} chunk",
                ("restore or re-export the complete PNG file; this chunk is truncated"),
            )
        crc = data[pos + 8 + length : pos + 12 + length]
        if len(crc) != 4:
            raise syntax_error(
                f"truncated {_chunk_label(kind)} chunk CRC",
                ("restore or re-export the complete PNG file including its checksums"),
            )
        if struct.unpack(">I", crc)[0] != zlib.crc32(kind + body) & 0xFFFFFFFF:
            raise syntax_error(
                f"invalid {_chunk_label(kind)} chunk CRC",
                (
                    "restore or re-export the PNG; its chunk checksum does not "
                    "match the data"
                ),
            )
        _time_remaining(deadline)
        if kind == b"IEND":
            if body:
                raise syntax_error("PNG IEND chunk must be empty", _REEXPORT)
            yield kind, body
            return
        yield kind, body
        pos += 12 + length  # length + type + body + CRC
    missing = "IHDR" if pos == len(_SIGNATURE) else "complete IEND"
    raise syntax_error(f"PNG has no {missing} chunk", _REEXPORT)


# Adam7's seven passes, each as (first row, first column, row step, column
# step).  Pass k stores a subsampled grid; together the seven tile the image
# exactly once, which is what lets a decoder show a coarse preview early.
_ADAM7 = (
    (0, 0, 8, 8),
    (0, 4, 8, 8),
    (4, 0, 8, 4),
    (0, 2, 4, 4),
    (2, 0, 4, 2),
    (0, 1, 2, 2),
    (1, 0, 2, 1),
)


def _pass_size(width: int, height: int, index: int) -> tuple[int, int]:
    """How many columns and rows Adam7 pass ``index`` holds."""
    row0, col0, row_step, col_step = _ADAM7[index]
    if width <= col0 or height <= row0:
        return 0, 0
    return (
        (width - col0 + col_step - 1) // col_step,
        (height - row0 + row_step - 1) // row_step,
    )


def _expected_stream_size(
    width: int, height: int, channels: int, depth: int, interlace: int
) -> int:
    """Return the stream length required by IHDR before allocating pixels."""
    if not interlace:
        stride = (width * channels * depth + 7) // 8
        return height * (stride + 1)
    total = 0
    for index in range(len(_ADAM7)):
        pass_width, pass_height = _pass_size(width, height, index)
        if pass_width and pass_height:
            stride = (pass_width * channels * depth + 7) // 8
            total += pass_height * (stride + 1)
    return total


def _scan_chunks(
    data: bytes,
) -> tuple[tuple[int, ...] | None, bytes | None, bytes]:
    """Collect the header, palette and compressed stream from the chunks."""
    header = None
    palette = None
    idat = bytearray()
    in_image_data = finished_image_data = False
    for index, (kind, body) in enumerate(_chunks(data)):
        if index == 0 and kind != b"IHDR":
            raise syntax_error("PNG IHDR must appear first and only once", _REEXPORT)
        if in_image_data and kind != b"IDAT":
            finished_image_data = True
        if kind == b"IHDR":
            if index != 0:
                raise syntax_error(
                    "PNG IHDR must appear first and only once", _REEXPORT
                )
            if len(body) != _IHDR.size:
                raise syntax_error(
                    f"PNG IHDR must be {_IHDR.size} bytes",
                    "restore or re-export the drawing as a valid PNG",
                )
            header = _IHDR.unpack(body)
        elif kind == b"PLTE":
            if palette is not None or in_image_data:
                raise syntax_error("PNG PLTE must appear once before IDAT", _REEXPORT)
            # PNG allows 1..256 RGB entries.  An over-long table made
            # ``read_grey`` build a >256-byte translate table (a raw
            # ``ValueError`` from ``bytes.translate``) while ``read_rgb``
            # silently ignored the extra.  Refuse it once, here.
            if not body or len(body) % 3 or len(body) > 768:
                raise syntax_error(
                    f"malformed PLTE chunk: {len(body)} bytes "
                    f"(want 3..768, a multiple of 3)",
                    "re-export as an 8-bit RGB PNG with a valid colour palette",
                )
            palette = body
        elif kind == b"IDAT":
            if finished_image_data:
                raise syntax_error("PNG IDAT chunks must be consecutive", _REEXPORT)
            in_image_data = True
            idat += body
        elif kind != b"IEND" and not kind[0] & 0x20:
            name = _chunk_label(kind)
            raise syntax_error(f"unknown PNG critical chunk {name}", _REEXPORT)
    if header is not None and not in_image_data:
        raise syntax_error("PNG has no IDAT chunk", _REEXPORT)
    return header, palette, bytes(idat)


def _check_header_fields(
    depth: int,
    colour: int,
    compression: int,
    filter_method: int,
    interlace: int,
) -> int:
    """Refuse header fields this decoder does not implement; return channels."""
    if compression != 0 or filter_method != 0:
        raise syntax_error(
            "unsupported PNG compression or filter method",
            (
                "re-export as a standard PNG with deflate compression and "
                "standard filters"
            ),
        )
    if interlace not in (0, 1):
        raise syntax_error(
            f"unknown PNG interlace method {interlace}",
            "re-export with no interlacing or standard Adam7 interlacing",
        )
    if colour not in _CHANNELS:
        raise syntax_error(
            f"unsupported PNG colour type {colour} "
            f"({_COLOUR_NAMES.get(colour, 'unknown')})",
            "re-export as an 8-bit RGB PNG",
        )
    if depth not in (1, 2, 4, 8, 16):
        raise syntax_error(
            f"unsupported PNG bit depth {depth}", "re-export as an 8-bit PNG"
        )

    channels = _CHANNELS[colour]
    if channels > 1 and depth < 8:
        # Sub-byte samples only occur in single-channel images per the spec.
        raise syntax_error(
            f"unsupported PNG bit depth {depth} for {channels} channels",
            "use 8-bit channels for RGB or RGBA images",
        )
    if colour == _PALETTE and depth == 16:
        raise syntax_error(
            "palette PNGs cannot be 16-bit", "use an 8-bit palette or export as RGB"
        )
    return channels


def _inflate_idat(idat: bytes, limit: int) -> tuple[bytes, bool]:
    """Keep each bounded inflate call small, including on highly compressed input."""
    decoder = zlib.decompressobj()
    deadline = _STREAM_DEADLINE.get()
    if deadline is None:
        return decoder.decompress(idat, limit), decoder.eof

    source = memoryview(idat)
    pending: bytes | memoryview = b""
    parts: list[bytes] = []
    offset = size = 0
    while size < limit and not decoder.eof:
        _time_remaining(deadline)
        if not pending:
            pending = source[offset : offset + _INFLATE_BLOCK]
            offset += len(pending)
        block = decoder.decompress(pending, min(limit - size, _INFLATE_BLOCK))
        pending = decoder.unconsumed_tail
        if not block and not pending and offset == len(source):
            break
        parts.append(block)
        size += len(block)
    _time_remaining(deadline)
    data = b"".join(parts)
    _time_remaining(deadline)
    return data, decoder.eof


def _inflate_checked(
    idat: bytes, needed: int, width: int, height: int, depth: int
) -> bytes:
    """Inflate the stream, refusing any size but the header's own count."""
    repair = "restore or re-export the complete PNG including its compressed checksum"
    # A 1x1 RGB header needs four bytes; a 39-byte IDAT expanded to 16,384
    # before its size was rejected. One surplus byte proves the mismatch.
    try:
        data_stream, complete = _inflate_idat(idat, min(needed + 1, sys.maxsize))
    except zlib.error as error:
        raise syntax_error(f"invalid PNG compressed stream: {error}", repair) from error
    if len(data_stream) != needed:
        # Reject before any allocation grows with the IHDR numbers.
        raise syntax_error(
            f"IDAT holds {len(data_stream)} bytes but {width}x{height} at "
            f"depth {depth} needs {needed}; the image is truncated or its "
            f"IHDR is corrupt",
            (
                "restore or re-export the PNG so the pixel data matches its "
                "declared dimensions"
            ),
        )
    if not complete:
        raise syntax_error("truncated PNG compressed stream", repair)
    return data_stream


def _check_row_filters(
    data_stream: bytes,
    width: int,
    height: int,
    channels: int,
    depth: int,
    interlace: int,
) -> None:
    """Walk the passes, refusing a row filter byte above 4."""
    deadline = _STREAM_DEADLINE.get()
    offset = 0
    passes = (
        [_pass_size(width, height, i) for i in range(len(_ADAM7))]
        if interlace
        else [(width, height)]
    )
    for pass_width, pass_height in passes:
        if not pass_width or not pass_height:
            continue
        stride = (pass_width * channels * depth + 7) // 8
        for row in range(pass_height):
            if deadline is not None and row % 1024 == 0:
                _time_remaining(deadline)
            if data_stream[offset] > 4:
                raise syntax_error(
                    f"unknown PNG row filter {data_stream[offset]}",
                    "re-export the PNG using standard row filters 0 through 4",
                )
            offset += stride + 1


def _check_pixel_limit(width: int, height: int, max_image_pixels: int | None) -> None:
    """Apply Pillow's hard limit before inflating or packing PNG pixels."""
    if max_image_pixels is None:
        return
    pixels = max(1, width) * max(1, height)
    limit = 2 * max_image_pixels
    # Above MAX_IMAGE_PIXELS itself, Pillow still permits reads with a warning.
    if pixels > limit:
        raise syntax_error(
            f"PNG size {width}x{height} ({pixels} pixels) exceeds the "
            f"{limit}-pixel PNG limit",
            "use a smaller raster",
            error_type=ProgramError,
        )


def _validate_png(
    data: bytes,
    max_image_pixels: int | None,
) -> tuple[int, int, int, bytes]:
    """Validate the container and stream before Pillow allocates pixels."""
    deadline = _STREAM_DEADLINE.get()
    header, palette, idat = _scan_chunks(data)
    if header is None:
        raise syntax_error(
            "PNG has no IHDR chunk",
            ("re-export the image with a PNG encoder so it includes the image header"),
        )
    width, height, depth, colour, compression, filter_method, interlace = header
    channels = _check_header_fields(
        depth, colour, compression, filter_method, interlace
    )
    _check_pixel_limit(width, height, max_image_pixels)
    needed = _expected_stream_size(width, height, channels, depth, interlace)
    _time_remaining(deadline)
    data_stream = _inflate_checked(idat, needed, width, height, depth)
    _time_remaining(deadline)
    if colour == _PALETTE and palette is None:
        raise syntax_error(
            "palette PNG has no PLTE chunk", "include a colour palette or export as RGB"
        )
    _check_row_filters(data_stream, width, height, channels, depth, interlace)
    return width, depth, colour, palette or b""


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


_METADATA_CHUNK = b"esOL"
_METADATA_LIMIT = 16_384
_JSON_TOKEN = re.compile(r"[^ \r\n\t]")
_JSON_ASCII_ESCAPE = re.compile(rb"[\x7f-\xff]+")


class SourceMetadataSizeError(ProgramError):
    """Source metadata exceeds the native PNG chunk budget."""


def _decode_metadata(body: bytes) -> dict[str, Any]:
    if len(body) > _METADATA_LIMIT:
        raise ValueError("duplicate or oversized esolangs PNG metadata")
    decoded = record_loads(body.decode("utf-8-sig"))
    if not isinstance(decoded, dict):
        raise ValueError("esolangs PNG metadata must be an object")
    try:
        check_record_utf8(decoded)
    except UnicodeEncodeError as error:
        raise ProgramError(f"PNG metadata is not valid UTF-8 text: {error}") from error
    return decoded


def _check_version(metadata: dict[str, Any]) -> None:
    version = metadata.get("version")
    if type(version) is not int or version < 1:
        raise ValueError("invalid esolangs PNG metadata version")
    if version != 1:
        raise ValueError("unsupported esolangs PNG metadata version")


def check_source_fields(metadata: dict[str, Any]) -> None:
    """Require the claims present on every source tag, including null values."""
    if not {"language", "settings", "scale"} <= metadata.keys():
        raise ValueError("esolangs PNG metadata requires language, settings and scale")


def read_metadata(data: Buffer) -> dict[str, Any] | None:
    """Read bounded UTF-8 version-one source metadata."""
    found: dict[str, Any] | None = None
    for kind, body in _chunks(_backing_bytes(data)):
        if kind != _METADATA_CHUNK:
            continue
        if found is not None:
            raise ValueError("duplicate or oversized esolangs PNG metadata")
        found = _decode_metadata(body)
    if found is not None:
        _check_version(found)
    return found


def write_metadata(data: Buffer, metadata: dict[str, Any]) -> bytes:
    """Append source metadata before IEND; image editors may discard it."""
    body = _encode_metadata(metadata)
    data = _backing_bytes(data)
    position, end = _metadata_span(data, locate_existing=False)
    return _write_metadata_chunk(data, body, position, end)


def _encode_metadata(metadata: dict[str, Any]) -> bytes:
    utf8 = _utf8_metadata(metadata)
    if len(utf8) > _METADATA_LIMIT:
        raise SourceMetadataSizeError("oversized esolangs PNG metadata")
    # Characters requiring ASCII escapes occur only inside JSON strings.
    # Escape this validated snapshot without reading caller containers again.
    body = _JSON_ASCII_ESCAPE.sub(
        lambda run: encode_basestring_ascii(run[0].decode())[1:-1].encode("ascii"),
        utf8,
    )
    return body if len(body) <= _METADATA_LIMIT else utf8


def _metadata_span(data: bytes, *, locate_existing: bool) -> tuple[int, int]:
    """Find the existing chunk or the insertion point before IEND."""
    # A PNG datastream can end before the last byte of its enclosing file.
    position = len(_SIGNATURE)
    previous = None
    for kind, contents in _chunks(data):
        if kind == b"IEND":
            break
        end = position + 12 + len(contents)
        if locate_existing and kind == _METADATA_CHUNK:
            if previous is not None:
                raise ProgramError("duplicate esolangs PNG metadata")
            previous = position, end
        position = end
    return (position, position) if previous is None else previous


def _write_metadata_chunk(data: bytes, body: bytes, start: int, end: int) -> bytes:
    if len(body) > _METADATA_LIMIT:
        raise SourceMetadataSizeError("oversized esolangs PNG metadata")
    chunk = _METADATA_CHUNK + body
    return (
        data[:start]
        + struct.pack(">I", len(body))
        + chunk
        + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
        + data[end:]
    )


def _utf8_metadata(metadata: dict[str, Any]) -> bytes:
    """Validate the same Unicode scalar values as portable metadata."""
    try:
        return record_dumps(metadata, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProgramError(f"PNG metadata is not valid UTF-8 text: {error}") from error


def _token_offset(text: str, position: int) -> int:
    match = _JSON_TOKEN.search(text, position)
    assert match is not None  # the complete object has already been decoded
    return match.start()


def _update_metadata_body(
    body: bytes,
    stored: dict[str, Any],
    additions: dict[str, Any],
    *,
    ensure_ascii: bool,
) -> bytes:
    """Edit only claim values, preserving legal extension numbers and spelling."""
    text = body.decode("utf-8")
    decoder = JSONDecoder(parse_int=str, parse_float=str)
    position = text.index("{") + 1
    start = 0
    parts = []
    for key in stored:
        _, key_end = decoder.raw_decode(text, _token_offset(text, position))
        value_start = _token_offset(text, _token_offset(text, key_end) + 1)
        _, value_end = decoder.raw_decode(text, value_start)
        position = _token_offset(text, value_end) + 1
        if key in additions:
            parts.append(text[start:value_start])
            parts.append(record_dumps(additions[key], ensure_ascii=ensure_ascii))
            start = value_end
    close = position - 1
    parts.append(text[start:close])
    new_fields = {key: value for key, value in additions.items() if key not in stored}
    if new_fields:
        parts.extend((",", record_dumps(new_fields, ensure_ascii=ensure_ascii)[1:-1]))
    parts.append(text[close:])
    return "".join(parts).encode("utf-8")


def _retained_owner(
    owner: Any, requested: str | None, *, catalog: Catalog | None
) -> str | None:
    if owner is None:
        return None
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("stored PNG language must be a nonblank string")
    if catalog is None:
        if requested is None or requested == owner:
            return owner
        from esolangs.registry._catalog import _same_origin_spelling

        if _same_origin_spelling(owner, requested):
            return owner
    else:
        from esolangs.registry._catalog import resolve_origin

        canonical = resolve_origin(owner, catalog=catalog)
        if canonical is None:
            raise ValueError(f"stored PNG language {owner!r} is not a catalog owner")
        if requested in (None, canonical):
            _check_png_owner(canonical, catalog, error_type=ValueError)
            return canonical
    raise ValueError(f"conflicting PNG language {owner!r} and {requested!r}")


def _check_png_owner(
    owner: str, catalog: Catalog, *, error_type: type[ValueError]
) -> None:
    from esolangs.runtime._definition import SourceKind

    if catalog.languages[owner].runtime.source_kind is not SourceKind.RASTER:
        raise error_type(
            f"{display_label(owner)} requires text source, but the program is a PNG"
        )


def _check_retained_settings(
    saved: Any, requested: Any, owner: str | None, *, catalog: Catalog | None
) -> None:
    from esolangs.settings import _decode_settings_choices, _settings_for

    if owner is None:
        raise ValueError("stored PNG settings need a language to apply to")
    choices = _decode_settings_choices(saved)
    if any(type(value) not in (int, str) for value in choices.values()):
        raise ValueError("stored PNG settings must be integer or string choices")
    if requested is not None and choices == _decode_settings_choices(requested):
        # Explicit settings already passed the catalog validator.
        return
    if catalog is not None:
        schema = catalog.languages[owner].runtime.dialect_schema
        if schema is not None and requested is None:
            _settings_for(owner, choices, catalog=catalog)
        elif schema is not None:
            schema.validate(choices)
        elif choices:
            raise ValueError(f"{display_label(owner)} declares no PNG dialect settings")
    if requested is not None:
        raise ValueError("conflicting PNG settings")


def _missing_claims(
    stored: dict[str, Any], requested: dict[str, Any], *, catalog: Catalog | None
) -> dict[str, Any]:
    owner = _retained_owner(
        stored.get("language"), requested["language"], catalog=catalog
    )
    for key in ("scale", "input_arity"):
        value = stored.get(key)
        if value is None and (key == "scale" or key not in stored):
            continue
        if type(value) is not int or value < 1:
            raise ValueError(f"stored PNG {key} must be a positive integer")
        if requested.get(key) not in (None, value):
            raise ValueError(f"conflicting PNG {key}")
    if (settings := stored.get("settings")) is not None:
        _check_retained_settings(
            settings, requested["settings"], owner, catalog=catalog
        )
    return {
        key: value
        for key, value in requested.items()
        if value is not None and stored.get(key) is None
    }


def _attach_metadata(
    data: Buffer, metadata: dict[str, Any], *, catalog: Catalog | None
) -> bytes:
    data = _backing_bytes(data)
    start, end = _metadata_span(data, locate_existing=True)
    if start == end:
        return _write_metadata_chunk(data, _encode_metadata(metadata), start, end)
    body = data[start + 8 : end - 4]
    with _track_acquisition_failures():
        try:
            stored = _decode_metadata(body)
            _check_version(stored)
            check_source_fields(stored)
            additions = _missing_claims(stored, metadata, catalog=catalog)
        except ProgramError:
            raise
        except (ValueError, RecursionError) as error:
            if _is_acquisition_failure(error):
                raise
            raise program_error_context(f"cannot tag PNG: {error}", error) from error
    if not additions:
        return data
    _utf8_metadata(additions)
    updated = _update_metadata_body(body, stored, additions, ensure_ascii=True)
    if len(updated) > _METADATA_LIMIT:
        updated = _update_metadata_body(body, stored, additions, ensure_ascii=False)
    return _write_metadata_chunk(data, updated, start, end)


def write_source(
    pixels: Rows,
    language: str | None,
    settings: DialectSettings | None,
    scale: int | None,
    *,
    input_arity: int | None = None,
    catalog: Catalog | None = None,
) -> bytes:
    """Encode pixels and explicit native source metadata without retagging."""
    try:
        claims = _source_claims(
            language, settings, scale, input_arity=input_arity, catalog=catalog
        )
        image = write_rgb(pixels)
        return (
            image
            if claims is None
            else _attach_metadata(image, claims, catalog=catalog)
        )
    except SourceMetadataSizeError as error:
        raise ProgramError(str(error)) from error


def attach_source_metadata(
    data: Buffer,
    language: str | None,
    settings: DialectSettings | None,
    scale: int | None,
    *,
    input_arity: int | None = None,
    catalog: Catalog | None = None,
) -> bytes:
    """Add absent source claims to PNG, checking settings in a supplied catalog."""
    claims = _source_claims(
        language, settings, scale, input_arity=input_arity, catalog=catalog
    )
    if claims is None:
        return _backing_bytes(data)
    return _attach_metadata(data, claims, catalog=catalog)


def _source_claims(
    language: str | None,
    settings: DialectSettings | None,
    scale: int | None,
    *,
    input_arity: int | None,
    catalog: Catalog | None,
) -> dict[str, Any] | None:
    """Validate incoming claims before acquiring image support or scanning PNG."""
    if catalog is not None:
        from esolangs.registry._catalog import get_catalog

        catalog = get_catalog(catalog)
    if language is None and settings is None and scale is None and input_arity is None:
        return None
    if language is not None:
        if not _has_backing_type(language, str):
            raise ArgumentError("PNG language must be a string")
        language = str.__str__(language)
        if not language.strip():
            raise ArgumentError("PNG language must be nonblank")
    if settings is not None:
        if not _has_backing_type(settings, DialectSettings):
            raise ArgumentError("settings must be a DialectSettings or None")
        owner = settings._schema.language  # noqa: SLF001
        spelling = owner if language is None else language
        if catalog is not None or spelling != owner:
            # An alias outside the owner's spelling needs its declared catalog.
            from esolangs.registry._catalog import _folded_spelling, get_catalog

            claimed = (
                owner
                if catalog is None
                and _folded_spelling(spelling) == _folded_spelling(owner)
                else get_catalog(catalog).resolve(spelling)
            )
            if claimed != owner:
                raise ArgumentError(
                    f"dialect settings belong to {display_label(owner)}, "
                    f"not {display_label(claimed)}"
                )
        language = owner
    elif catalog is not None and language is not None:
        language = catalog.resolve(language)
    metadata: dict[str, Any] = {
        "version": 1,
        "language": language,
        "settings": None
        if settings is None
        else {
            key: {"integer": hex(value)} if type(value) is int else value
            for key, value in settings._items  # noqa: SLF001
        },
        "scale": None if scale is None else check_scale(scale),
    }
    if input_arity is not None:
        metadata["input_arity"] = check_input_arity(input_arity)
    if catalog is not None and language is not None:
        _check_png_owner(language, catalog, error_type=ArgumentError)
        if settings is not None:
            from esolangs.settings import dialect_options

            dialect_options(language, settings, catalog=catalog)
    return metadata
