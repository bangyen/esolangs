"""A minimal PNG reader and writer, so Line's tooling needs no image library.

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

import numpy as np

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
) -> np.ndarray:
    """Expand sub-byte samples to one array element each, dropping row padding."""
    packed = np.frombuffer(bytes(rows), dtype=np.uint8).reshape(height, stride)
    per_byte = 8 // depth
    # Most-significant bits first, per the spec.
    shifts = np.arange(per_byte - 1, -1, -1, dtype=np.uint8) * depth
    expanded = (packed[:, :, None] >> shifts) & ((1 << depth) - 1)
    return expanded.reshape(height, stride * per_byte)[:, :width]


def read_grey(data: bytes) -> np.ndarray:
    """Decode PNG bytes to a 2-D ``uint8`` array of greyscale values.

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
    rows = _unfilter(zlib.decompress(bytes(idat)), height, stride, step=1)
    samples = (
        np.frombuffer(bytes(rows), dtype=np.uint8).reshape(height, stride)[:, :width]
        if depth == 8
        else _unpack_bits(rows, height, width, stride, depth)
    )

    if colour == _PALETTE:
        if palette is None:
            raise ValueError("palette PNG has no PLTE chunk")
        table = np.frombuffer(palette, dtype=np.uint8).reshape(-1, 3).astype(np.uint32)
        # ITU-R 601-2 luma, matching Pillow's RGB -> L conversion.
        luma = (table[:, 0] * 299 + table[:, 1] * 587 + table[:, 2] * 114) // 1000
        return np.asarray(luma.astype(np.uint8)[samples], dtype=np.uint8)
    if depth != 8:
        # Scale a narrow greyscale range up to full 0-255 (1-bit 1 -> 255).
        scaled = samples * (255 // ((1 << depth) - 1))
        return np.asarray(scaled, dtype=np.uint8)
    return np.asarray(samples, dtype=np.uint8)


def write_grey(pixels: np.ndarray) -> bytes:
    """Encode a 2-D ``uint8`` array as 8-bit greyscale PNG bytes.

    Every row is written with filter type 0 (None).  Filtering exists to help
    the compressor, and these drawings are near-empty white canvases that zlib
    already collapses; picking a filter per row would add a heuristic for no
    benefit anyone here can see.
    """
    array = np.ascontiguousarray(pixels, dtype=np.uint8)
    if array.ndim != 2:
        raise ValueError("expected a 2-D greyscale array")
    height, width = array.shape

    raw = bytearray()
    for row in array:
        raw.append(0)  # filter type: None
        raw += row.tobytes()

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


def read_grey_file(path: str) -> np.ndarray:
    """Read a PNG file from ``path`` as a 2-D ``uint8`` greyscale array."""
    with open(path, "rb") as handle:
        return read_grey(handle.read())


def write_grey_file(path: str, pixels: np.ndarray) -> None:
    """Write a 2-D ``uint8`` greyscale array to ``path`` as a PNG."""
    with open(path, "wb") as handle:
        handle.write(write_grey(pixels))
