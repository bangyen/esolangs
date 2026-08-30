"""A minimal PNG reader and writer, so Line's tooling needs no image library.

Images are passed as one ``bytearray`` of greyscale levels per row -- the
same shape ``render.Canvas`` keeps its pixels in, and what
``mask.from_grey`` thresholds into an ink mask.

Only what ``extract.py`` and ``render.py`` actually exchange is supported:
non-interlaced images that are 1/2/4/8-bit greyscale or palette-indexed on
the way in, and 8-bit greyscale on the way out.  That covers the wiki
reference images checked in under ``fixtures/`` (1-bit palette, black and
white) and everything :func:`render.render` produces.  Anything else --
interlaced, 16-bit, truecolour, an alpha channel -- raises rather than
guessing, since a Line drawing that arrives in one of those formats is far
more likely to be a mistake than something worth silently accepting.

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
    against the row above it, so this cannot be vectorised across rows the way
    the rest of this module's array work is -- filters 1/3/4 also depend on
    earlier bytes *within* the same row.  ``step`` is the byte distance to the
    pixel on the left (1 for every format here, since all are single-channel
    at 8 bits or narrower, but the spec defines it per-format).
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


def _unpack_bits(
    rows: bytearray, height: int, width: int, stride: int, depth: int
) -> list[bytearray]:
    """Expand sub-byte samples to one byte each, dropping each row's padding.

    Every byte expands the same way regardless of where it sits, so the 256
    possible expansions are tabulated once and the per-row work becomes a
    lookup and a join rather than a shift per sample.
    """
    per_byte = 8 // depth
    mask = (1 << depth) - 1
    # Most-significant sample first, per the spec.
    table = [
        bytes(
            (value >> (shift * depth)) & mask for shift in range(per_byte - 1, -1, -1)
        )
        for value in range(256)
    ]
    out = []
    for y in range(height):
        packed = rows[y * stride : (y + 1) * stride]
        out.append(bytearray(b"".join([table[byte] for byte in packed])[:width]))
    return out


def read_grey(data: bytes) -> list[bytearray]:
    """Decode PNG bytes to one ``bytearray`` of greyscale levels per row.

    Palette images are resolved through their PLTE entries; because the only
    palettes this needs to handle are black-and-white, the RGB triple is
    reduced with the same ITU-R 601-2 luma weights Pillow's ``convert("L")``
    uses, so a greyscale threshold means the same thing either way.
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
    if interlace != 0:
        raise ValueError("interlaced PNGs are not supported")
    if colour not in (_GREY, _PALETTE):
        raise ValueError(
            f"unsupported PNG colour type {colour} "
            f"({_COLOUR_NAMES.get(colour, 'unknown')}); "
            "only greyscale and palette images are supported"
        )
    if depth not in (1, 2, 4, 8):
        raise ValueError(f"unsupported PNG bit depth {depth}")

    stride = (width * depth + 7) // 8
    raw = _unfilter(zlib.decompress(bytes(idat)), height, stride, step=1)
    if depth == 8:
        samples = [
            bytearray(raw[y * stride : y * stride + width]) for y in range(height)
        ]
    else:
        samples = _unpack_bits(raw, height, width, stride, depth)

    if colour == _PALETTE:
        if palette is None:
            raise ValueError("palette PNG has no PLTE chunk")
        entries = [palette[i : i + 3] for i in range(0, len(palette), 3)]
        # ITU-R 601-2 luma, matching Pillow's RGB -> L conversion.  Padded out
        # to a full 256 entries because that is what bytes.translate wants; a
        # sample indexing past the palette is a malformed file, and mapping it
        # to black is as good as any other answer for one.
        luma = bytes(
            (red * 299 + green * 587 + blue * 114) // 1000
            for red, green, blue in entries
        ).ljust(256, b"\x00")
        return [row.translate(luma) for row in samples]
    if depth != 8:
        # Scale a narrow greyscale range up to full 0-255 (1-bit 1 -> 255).
        factor = 255 // ((1 << depth) - 1)
        scale = bytes((value * factor) & 0xFF for value in range(256))
        return [row.translate(scale) for row in samples]
    return samples


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
