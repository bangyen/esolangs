"""Validate PNG image data before allocating decoded pixels."""

import struct
import sys
import zlib

from esolangs.exceptions import ProgramError
from esolangs.raster._png_chunks import _REEXPORT, _chunk_label, _chunks
from esolangs.runtime._files import _STREAM_DEADLINE, _time_remaining
from esolangs.runtime.source_hints import syntax_error

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
