"""PNG I/O through the optional image extra; alpha is discarded."""

from __future__ import annotations

import io
import re
import struct
import sys
import zlib
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any

from esolangs.exceptions import MissingDependencyError
from esolangs.interpreters.source_hints import syntax_error

if TYPE_CHECKING:
    from esolangs.raster import Pixel, Rows

_UNLOADED = object()
Image: Any = _UNLOADED


def _require_image() -> Any:
    """Return Pillow or name the extra that installs it."""
    global Image
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


def _chunks(data: bytes) -> Iterator[tuple[bytes, bytes]]:
    """Yield ``(type, body)`` for each chunk, checking the signature first."""
    if data[:8] != _SIGNATURE:
        raise syntax_error(
            "not a PNG file (bad signature)",
            "export the image as PNG instead of renaming another image format",
        )
    pos = 8
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if len(body) != length:
            raise syntax_error(
                f"truncated {kind.decode('ascii', 'replace')} chunk",
                ("restore or re-export the complete PNG file; this chunk is truncated"),
            )
        crc = data[pos + 8 + length : pos + 12 + length]
        if len(crc) != 4:
            raise syntax_error(
                f"truncated {kind.decode('ascii', 'replace')} chunk CRC",
                ("restore or re-export the complete PNG file including its checksums"),
            )
        if struct.unpack(">I", crc)[0] != zlib.crc32(kind + body) & 0xFFFFFFFF:
            raise syntax_error(
                f"invalid {kind.decode('ascii', 'replace')} chunk CRC",
                (
                    "restore or re-export the PNG; its chunk checksum does not "
                    "match the data"
                ),
            )
        yield kind, body
        pos += 12 + length  # length + type + body + CRC


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


def _validate_png(
    data: bytes,
) -> tuple[int, int, int, bytes]:
    """Validate the container and stream before Pillow allocates pixels."""
    header = None
    palette = None
    idat = bytearray()
    for kind, body in _chunks(data):
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
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
            idat += body
        elif kind == b"IEND":
            break
    if header is None:
        raise syntax_error(
            "PNG has no IHDR chunk",
            ("re-export the image with a PNG encoder so it includes the image header"),
        )
    width, height, depth, colour, compression, filter_method, interlace = header

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

    needed = _expected_stream_size(width, height, channels, depth, interlace)
    decoder = zlib.decompressobj()
    # A 1x1 RGB header needs four bytes; a 39-byte IDAT expanded to 16,384
    # before its size was rejected. One surplus byte proves the mismatch.
    data_stream = decoder.decompress(bytes(idat), min(needed + 1, sys.maxsize))
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
    if not decoder.eof:
        raise syntax_error(
            "truncated PNG compressed stream",
            "restore or re-export the complete PNG including its compressed checksum",
        )
    if colour == _PALETTE and palette is None:
        raise syntax_error(
            "palette PNG has no PLTE chunk", "include a colour palette or export as RGB"
        )
    offset = 0
    passes = (
        [_pass_size(width, height, i) for i in range(7)]
        if interlace
        else [(width, height)]
    )
    for pass_width, pass_height in passes:
        if not pass_width or not pass_height:
            continue
        stride = (pass_width * channels * depth + 7) // 8
        for _ in range(pass_height):
            if data_stream[offset] > 4:
                raise syntax_error(
                    f"unknown PNG row filter {data_stream[offset]}",
                    "re-export the PNG using standard row filters 0 through 4",
                )
            offset += stride + 1
    return width, depth, colour, palette or b""


def _read(data: bytes, mode: str) -> tuple[bytes, int]:
    image = _require_image()
    width, depth, colour, palette = _validate_png(data)
    with image.open(io.BytesIO(data), formats=["PNG"]) as opened:
        opened.load()
        if colour == _PALETTE and max(opened.tobytes()) >= len(palette) // 3:
            raise syntax_error(
                "palette index outside PLTE chunk",
                ("re-export the PNG so every palette index has a corresponding colour"),
            )
        if colour == _GREY and depth == 16:
            # I;16 -> L clips; taking the high byte preserves dark strokes.
            raw = opened.tobytes("raw", "I;16B")
            with image.frombytes("L", opened.size, raw[0::2]) as grey:
                return grey.convert(mode).tobytes(), width
        return opened.convert(mode).tobytes(), width


def read_grey(data: bytes) -> list[bytearray]:
    """Decode PNG bytes to rows of greyscale levels, ignoring alpha."""
    raw, width = _read(data, "L")
    return [bytearray(raw[i : i + width]) for i in range(0, len(raw), width)]


_RGB_RUN = re.compile(rb"(.{3})\1*", re.DOTALL)


def _rgb_rows(data: bytes) -> Rows:
    """Decode immutable RGB rows, reusing up to 1024 pixels and row patterns."""
    raw, width = _read(data, "RGB")
    palette: dict[bytes, Pixel] = {}
    patterns: dict[bytes, tuple[Pixel, ...]] = {}
    rows = []
    stride = width * 3
    for offset in range(0, len(raw), stride):
        scanline = raw[offset : offset + stride]
        row = patterns.get(scanline)
        if row is None:
            pixels = []
            for run in _RGB_RUN.finditer(scanline):
                key = run[1]
                pixel = palette.get(key)
                if pixel is None:
                    if len(palette) == 1024:
                        pixels = list(zip(raw[0::3], raw[1::3], raw[2::3], strict=True))
                        return tuple(
                            tuple(pixels[i : i + width])
                            for i in range(0, len(pixels), width)
                        )
                    pixel = (key[0], key[1], key[2])
                    palette[key] = pixel
                pixels.extend([pixel] * ((run.end() - run.start()) // 3))
            row = tuple(pixels)
            if len(patterns) < 1024:
                patterns[scanline] = row
        rows.append(row)
    return tuple(rows)


def read_rgb(data: bytes) -> list[list[tuple[int, int, int]]]:
    """Decode PNG bytes to independent mutable RGB rows, ignoring alpha."""
    return [list(row) for row in _rgb_rows(data)]


def _write(mode: str, width: int, height: int, raw: bytes) -> bytes:
    image = _require_image()
    output = io.BytesIO()
    with image.frombytes(mode, (width, height), raw) as opened:
        opened.save(output, format="PNG")
    return output.getvalue()


def write_grey(pixels: list[bytearray]) -> bytes:
    """Encode rectangular greyscale rows as PNG bytes."""
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    if not height or not width or any(len(row) != width for row in pixels):
        raise syntax_error(
            "expected a non-empty 2-D greyscale image with equal-length rows",
            "provide nonempty, equal-width rows of greyscale pixels",
        )
    return _write("L", width, height, b"".join(pixels))


def write_grey_file(path: str, pixels: list[bytearray]) -> None:
    """Write greyscale rows to ``path`` as a PNG."""
    data = write_grey(pixels)
    with open(path, "wb") as handle:
        handle.write(data)


def write_rgb(pixels: Sequence[Sequence[tuple[int, int, int]]]) -> bytes:
    """Encode rectangular 8-bit RGB rows as PNG bytes."""
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    if not height or not width or any(len(row) != width for row in pixels):
        raise syntax_error(
            "expected a non-empty 2-D RGB image",
            "provide nonempty, equal-width rows of RGB pixels",
        )
    packed_rows: dict[int, tuple[Sequence[tuple[int, int, int]], bytes]] = {}
    packed_pixels: dict[int, tuple[tuple[int, int, int], bytes]] = {}
    cache_pixels = True
    parts = []
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
        for pixel in row:
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
            if len(pixel) != 3 or any(not 0 <= value <= 255 for value in pixel):
                raise syntax_error(
                    f"invalid RGB pixel {pixel!r}",
                    "use three integer RGB channels from 0 through 255",
                )
            raw.extend(pixel)
            if type(pixel) is tuple:
                if cache_pixels:
                    previous = pixel
                    previous_bytes = bytes(pixel)
                    packed_pixels[id(pixel)] = pixel, previous_bytes
                    cache_pixels = len(packed_pixels) < 1024
            else:
                immutable = False
        if repeats:
            raw.extend(previous_bytes * repeats)
        packed = bytes(raw)
        parts.append(packed)
        if immutable and len(packed_rows) < 1024:
            packed_rows[id(row)] = row, packed
    return _write("RGB", width, height, b"".join(parts))
