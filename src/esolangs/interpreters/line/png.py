"""A minimal PNG reader and writer, so Line's tooling needs no image library.

Images are passed as one ``bytearray`` of greyscale levels per row -- the
same shape ``render.Canvas`` keeps its pixels in, and what
``mask.from_grey`` thresholds into an ink mask.

Reading accepts any PNG the spec defines -- every colour type, every bit
depth from 1 to 16, interlaced or not -- and reduces it to greyscale on the
way in; writing always emits plain 8-bit greyscale.  Reading broadly matters
because a Line drawing that has been through an image editor comes back in
whatever that editor prefers (commonly RGB, sometimes 16-bit) while still
being visually the same black-and-white drawing.

The point is not to be a general codec.  PNG's container is a handful of
length-tagged chunks and its compression is plain zlib, both in the standard
library; the only real work is undoing the per-row filters, which is the
loop in :func:`_unfilter`.  That is small enough to be worth owning outright
rather than depending on Pillow to do -- see the dependency notes in
``extract.py``.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Iterator

_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Colour type codes from the PNG spec (IHDR byte 9).  Only the two
# single-channel ones are handled; the rest are named to make the rejection
# message in :func:`read_grey` specific about what was found.
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


def _luma(red: int, green: int, blue: int) -> int:
    """Reduce a colour to grey with ITU-R 601-2 weights, as Pillow does.

    Pillow's ``convert("L")`` uses this exact fixed-point form rather than a
    float or a floor-divided decimal; the ``+ 0x8000`` rounds to nearest.
    Cheaper formulas agree on pure black and white but differ by one level on
    mid-greys, which is enough to flip a pixel across the ink threshold.
    """
    return (red * 19595 + green * 38470 + blue * 7471 + 0x8000) >> 16


def _chunks(data: bytes) -> Iterator[tuple[bytes, bytes]]:
    """Yield ``(type, body)`` for each chunk, checking the signature first."""
    if data[:8] != _SIGNATURE:
        raise ValueError("not a PNG file (bad signature)")
    pos = 8
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if len(body) != length:
            raise ValueError(f"truncated {kind.decode('ascii', 'replace')} chunk")
        yield kind, body
        pos += 12 + length  # length + type + body + CRC


def _paeth(a: int, b: int, c: int) -> int:
    """Predict a byte the way the PNG spec's Paeth filter does.

    Returns whichever of left/up/up-left is closest to ``a + b - c``.
    """
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw: bytes, height: int, stride: int, step: int) -> bytearray:
    """Reverse the per-row filters, returning ``height * stride`` raw bytes.

    Each row in ``raw`` is prefixed with a filter-type byte and is decoded
    against the row above it, and filters 1/3/4 also depend on earlier bytes
    *within* the same row, so this is inherently sequential.  ``step`` is the
    byte distance to the pixel on the left: one whole pixel, which is
    ``channels * depth // 8`` bytes, floored at 1 because sub-byte pixels
    predict from the neighbouring byte.
    """
    out = bytearray(height * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        filter_type = raw[pos]
        pos += 1
        row = bytearray(raw[pos : pos + stride])
        pos += stride
        if filter_type == 0:  # None
            pass
        elif filter_type == 1:  # Sub
            for i in range(step, stride):
                row[i] = (row[i] + row[i - step]) & 0xFF
        elif filter_type == 2:  # Up
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif filter_type == 3:  # Average
            for i in range(stride):
                left = row[i - step] if i >= step else 0
                row[i] = (row[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filter_type == 4:  # Paeth
            for i in range(stride):
                left = row[i - step] if i >= step else 0
                upleft = prev[i - step] if i >= step else 0
                row[i] = (row[i] + _paeth(left, prev[i], upleft)) & 0xFF
        else:
            raise ValueError(f"unknown PNG row filter {filter_type}")
        out[y * stride : (y + 1) * stride] = row
        prev = row
    return out


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


def _unpack_row(raw: bytes, width: int, channels: int, depth: int) -> list[int]:
    """Expand one filtered-and-restored row to one integer per sample."""
    count = width * channels
    if depth == 8:
        return list(raw[:count])
    if depth == 16:
        # Big-endian, per the spec.
        return [(raw[2 * i] << 8) | raw[2 * i + 1] for i in range(count)]
    per_byte = 8 // depth
    mask = (1 << depth) - 1
    out: list[int] = []
    for byte in raw:
        # Most-significant sample first, per the spec.
        for shift in range(per_byte - 1, -1, -1):
            out.append((byte >> (shift * depth)) & mask)
    return out[:count]  # trailing samples are row padding


def _read_pass(
    stream: bytes, width: int, height: int, channels: int, depth: int, offset: int = 0
) -> list[list[int]]:
    """Decode one non-interlaced image (or one Adam7 pass) from ``stream``.

    ``offset`` is where this pass's filtered rows start; a whole
    non-interlaced image is just the single pass beginning at zero.
    """
    if width == 0 or height == 0:
        return []
    stride = (width * channels * depth + 7) // 8
    # The filter predictor looks one *pixel* to the left, which is the pixel's
    # whole width in bytes -- never less than one, since sub-byte pixels
    # predict from the adjacent byte.
    step = max(1, channels * depth // 8)
    raw = _unfilter(stream[offset:], height, stride, step)
    return [
        _unpack_row(bytes(raw[y * stride : (y + 1) * stride]), width, channels, depth)
        for y in range(height)
    ]


def _pass_size(width: int, height: int, index: int) -> tuple[int, int]:
    """How many columns and rows Adam7 pass ``index`` holds."""
    row0, col0, row_step, col_step = _ADAM7[index]
    if width <= col0 or height <= row0:
        return 0, 0
    return (
        (width - col0 + col_step - 1) // col_step,
        (height - row0 + row_step - 1) // row_step,
    )


def _deinterlace(
    stream: bytes, width: int, height: int, channels: int, depth: int
) -> list[list[int]]:
    """Reassemble the seven Adam7 passes into ordinary scanlines.

    Each pass is a complete little image with its own dimensions, its own row
    filters and its own row padding, laid end to end in the same zlib stream,
    so each is decoded exactly like a non-interlaced one and its pixels are
    then scattered onto the lattice it came from.
    """
    rows = [[0] * (width * channels) for _ in range(height)]
    offset = 0
    for index, (row0, col0, row_step, col_step) in enumerate(_ADAM7):
        pass_width, pass_height = _pass_size(width, height, index)
        if pass_width == 0 or pass_height == 0:
            continue
        decoded = _read_pass(stream, pass_width, pass_height, channels, depth, offset)
        for y, row in enumerate(decoded):
            target = rows[row0 + y * row_step]
            for x in range(pass_width):
                base = (col0 + x * col_step) * channels
                target[base : base + channels] = row[x * channels : (x + 1) * channels]
        stride = (pass_width * channels * depth + 7) // 8
        offset += pass_height * (stride + 1)  # each row carries a filter byte
    return rows


def read_grey(data: bytes) -> list[bytearray]:
    """Decode PNG bytes to one ``bytearray`` of greyscale levels per row.

    Colour is reduced with the same ITU-R 601-2 luma weights Pillow's
    ``convert("L")`` uses -- palette entries included -- so an ink threshold
    means the same thing whichever format a drawing arrives in.
    """
    header = None
    palette = None
    idat = bytearray()
    for kind, body in _chunks(data):
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = body
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    if header is None:
        raise ValueError("PNG has no IHDR chunk")
    width, height, depth, colour, compression, filter_method, interlace = header

    if compression != 0 or filter_method != 0:
        raise ValueError("unsupported PNG compression or filter method")
    if interlace not in (0, 1):
        raise ValueError(f"unknown PNG interlace method {interlace}")
    if colour not in _CHANNELS:
        raise ValueError(
            f"unsupported PNG colour type {colour} "
            f"({_COLOUR_NAMES.get(colour, 'unknown')})"
        )
    if depth not in (1, 2, 4, 8, 16):
        raise ValueError(f"unsupported PNG bit depth {depth}")

    channels = _CHANNELS[colour]
    if channels > 1 and depth < 8:
        # Sub-byte samples only occur in single-channel images per the spec.
        raise ValueError(f"unsupported PNG bit depth {depth} for {channels} channels")
    if colour == _PALETTE and depth == 16:
        raise ValueError("palette PNGs cannot be 16-bit")

    data_stream = zlib.decompress(bytes(idat))
    if interlace:
        samples = _deinterlace(data_stream, width, height, channels, depth)
    else:
        samples = _read_pass(data_stream, width, height, channels, depth)

    return _to_grey(samples, width, channels, depth, colour, palette)


def _to_grey(
    samples: list[list[int]],
    width: int,
    channels: int,
    depth: int,
    colour: int,
    palette: bytes | None,
) -> list[bytearray]:
    """Reduce decoded samples to one greyscale byte per pixel.

    ``samples`` holds one row per scanline, already unpacked to one integer
    per sample and with any row padding dropped.
    """
    if colour == _PALETTE:
        if palette is None:
            raise ValueError("palette PNG has no PLTE chunk")
        entries = [palette[i : i + 3] for i in range(0, len(palette), 3)]
        # Padded out to a full 256 entries because that is what bytes.translate
        # wants; a sample indexing past the palette is a malformed file, and
        # mapping it to black is as good as any other answer for one.
        table = bytes(_luma(*entry) for entry in entries).ljust(256, b"\x00")
        return [bytearray(row).translate(table) for row in samples]

    # Bring every depth onto the same 0-255 scale before reducing colour, so
    # the luma weights and the ink threshold mean one thing throughout.
    top = (1 << depth) - 1
    if depth == 8:

        def level(value: int) -> int:
            return value
    elif depth == 16:
        # Take the high byte, i.e. scale 0-65535 down onto 0-255.  This is a
        # deliberate departure from Pillow, whose I;16 -> L conversion *clips*
        # rather than scaling: under Pillow every 16-bit value above 255 comes
        # out white, so a drawing whose ink is stored as, say, 1000 decodes to
        # a blank page with every stroke erased.  Scaling keeps the picture.
        # The two agree on pure 0 and pure 65535, which is what a clean
        # black-and-white drawing actually contains, so this only ever differs
        # in Pillow's favour on files Pillow would have mangled.
        def level(value: int) -> int:
            return value >> 8
    else:

        def level(value: int) -> int:
            return value * 255 // top

    if colour in (_RGB, _RGBA):
        # Alpha is dropped rather than composited, matching Pillow's
        # convert("L"): a Line drawing's transparency is not ink.
        return [
            bytearray(
                _luma(level(row[i]), level(row[i + 1]), level(row[i + 2]))
                for i in range(0, width * channels, channels)
            )
            for row in samples
        ]
    if colour == _GREY_ALPHA:
        return [bytearray(level(v) for v in row[0 : width * 2 : 2]) for row in samples]
    return [bytearray(level(v) for v in row[:width]) for row in samples]


def write_grey(pixels: list[bytearray]) -> bytes:
    """Encode one ``bytearray`` of greyscale levels per row as 8-bit PNG bytes.

    Every row is written with filter type 0 (None).  Filtering exists to help
    the compressor, and these drawings are near-empty white canvases that zlib
    already collapses; picking a filter per row would add a heuristic for no
    benefit anyone here can see.
    """
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    if any(len(row) != width for row in pixels):
        raise ValueError("expected a 2-D greyscale image with equal-length rows")

    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter type: None
        raw += row

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, _GREY, 0, 0, 0)
    return (
        _SIGNATURE
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def read_grey_file(path: str) -> list[bytearray]:
    """Read a PNG file from ``path`` as one ``bytearray`` of levels per row."""
    with open(path, "rb") as handle:
        return read_grey(handle.read())


def write_grey_file(path: str, pixels: list[bytearray]) -> None:
    """Write greyscale rows to ``path`` as a PNG."""
    with open(path, "wb") as handle:
        handle.write(write_grey(pixels))
