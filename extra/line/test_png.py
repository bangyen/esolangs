"""Tests for png.py.

Run via: uv run --with numpy --with pytest pytest test_png.py

png.py replaced Pillow (see the dependency notes in extract.py), so what
needs guarding is that it still reads the checked-in wiki fixtures the way
Pillow did and round-trips what render.py writes.  Pillow is not available
to compare against here, so the fixture expectations below are the values
Pillow produced when the swap was made, recorded as constants.

Beyond that: every row filter the spec defines (the fixtures between them
use 0/1/2/4, but a PNG this reads could legitimately use 3), the sub-byte
bit depths, and the rejections -- an unsupported format must raise rather
than decode something plausible-looking but wrong.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np
import png
import pytest

FIXTURES = Path(__file__).parent / "fixtures"

# Shape and ink count (pixels below the 128 threshold extract.py uses) for
# each checked-in fixture, as decoded by Pillow's Image.open().convert("L")
# before png.py replaced it.
FIXTURE_EXPECTATIONS = {
    "addition.png": ((300, 300), 926),
    "addition_2x.png": ((600, 600), 3704),
    "addition_3x.png": ((900, 900), 8334),
    "multiplication.png": ((500, 500), 2724),
    "multiplication_2x.png": ((1000, 1000), 10896),
}


@pytest.mark.parametrize(("name", "expected"), FIXTURE_EXPECTATIONS.items())
def test_reads_wiki_fixtures_as_pillow_did(
    name: str, expected: tuple[tuple[int, int], int]
) -> None:
    """Each fixture decodes to the shape and ink count Pillow reported."""
    shape, ink = expected
    grey = png.read_grey_file(str(FIXTURES / name))
    assert grey.shape == shape
    assert grey.dtype == np.uint8
    assert int((grey < 128).sum()) == ink
    # These are 1-bit black-and-white images: nothing in between.
    assert set(np.unique(grey).tolist()) == {0, 255}


@pytest.mark.parametrize("shape", [(1, 1), (3, 7), (64, 65), (200, 133)])
def test_roundtrip_preserves_every_byte(shape: tuple[int, int]) -> None:
    """Writing then reading an arbitrary greyscale array is the identity."""
    rng = np.random.default_rng(0)
    original = rng.integers(0, 256, size=shape, dtype=np.uint8)
    assert np.array_equal(png.read_grey(png.write_grey(original)), original)


def test_roundtrip_through_a_file(tmp_path: Path) -> None:
    """The file-level helpers agree with the in-memory pair."""
    path = tmp_path / "out.png"
    original = np.array([[0, 128], [255, 7]], dtype=np.uint8)
    png.write_grey_file(str(path), original)
    assert np.array_equal(png.read_grey_file(str(path)), original)


def _encode(
    rows: list[bytes], width: int, height: int, depth: int = 8, colour: int = 0
) -> bytes:
    """Build a PNG from already-filtered rows (each prefixed by its filter byte)."""

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, depth, colour, 0, 0, 0)
    return (
        png._SIGNATURE  # noqa: SLF001 - building a PNG by hand
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize("filter_type", [0, 1, 2, 3, 4])
def test_every_row_filter_decodes(filter_type: int) -> None:
    """All five spec filters reconstruct the same image.

    Each row is filtered by hand here rather than trusting an encoder, so a
    wrong predictor in :func:`png._unfilter` shows up as wrong pixels rather
    than being masked by a matching bug on the write side.

    The pixel values are chosen to exercise Average's floor-vs-round on an
    odd ``left + up`` (e.g. 3 + 200), which a smooth gradient hides -- and
    which mutation confirmed this catches.

    Paeth's first ``<=`` is deliberately *not* covered, because it cannot be:
    ``pa == pb`` requires ``|b - c| == |a - c|`` with ``p = a + b - c``, which
    forces ``a == b``, so the branch returns the same value either way.
    Weakening it to ``<`` is an equivalent mutation over all 256^3 inputs
    (checked exhaustively), not a gap in these cases.
    """
    want = np.array(
        [
            [3, 200, 3, 255],
            [200, 3, 100, 0],
            [7, 250, 130, 130],
            [130, 130, 4, 251],
        ],
        dtype=np.uint8,
    )
    height, width = want.shape
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            value = int(want[y, x])
            left = int(want[y, x - 1]) if x else 0
            up = int(want[y - 1, x]) if y else 0
            upleft = int(want[y - 1, x - 1]) if y and x else 0
            if filter_type == 0:
                row.append(value)
            elif filter_type == 1:
                row.append((value - left) & 0xFF)
            elif filter_type == 2:
                row.append((value - up) & 0xFF)
            elif filter_type == 3:
                row.append((value - ((left + up) >> 1)) & 0xFF)
            else:
                row.append((value - png._paeth(left, up, upleft)) & 0xFF)  # noqa: SLF001
        rows.append(bytes([filter_type]) + bytes(row))
    assert np.array_equal(png.read_grey(_encode(rows, width, height)), want)


@pytest.mark.parametrize(
    ("depth", "packed", "expected"),
    [
        # Sub-byte samples are most-significant-bit first, and the row is
        # padded out to a whole byte -- the padding must not leak into the
        # decoded width.
        (1, 0b10100000, [255, 0, 255]),
        (2, 0b11000100, [255, 0, 85]),
        (4, 0b11110000, [255, 0]),
    ],
)
def test_sub_byte_depths_unpack_and_scale(
    depth: int, packed: int, expected: list[int]
) -> None:
    """Narrow greyscale depths expand to the full 0-255 range."""
    width = len(expected)
    blob = _encode([bytes([0, packed])], width, 1, depth=depth)
    assert png.read_grey(blob).tolist() == [expected]


def test_palette_is_resolved_through_plte() -> None:
    """A palette image maps indices through PLTE, not straight to greyscale."""

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    # Index 0 -> white, index 1 -> black: the fixtures' own palette.
    blob = (
        png._SIGNATURE  # noqa: SLF001 - building a PNG by hand
        + chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", 2, 1, 1, png._PALETTE, 0, 0, 0),  # noqa: SLF001
        )
        + chunk(b"PLTE", bytes([255, 255, 255, 0, 0, 0]))
        + chunk(b"IDAT", zlib.compress(bytes([0, 0b01000000])))
        + chunk(b"IEND", b"")
    )
    assert png.read_grey(blob).tolist() == [[255, 0]]


def test_rejects_a_non_png() -> None:
    """Bytes that are not a PNG at all are refused up front."""
    with pytest.raises(ValueError, match="signature"):
        png.read_grey(b"not a png at all")


def test_rejects_interlaced() -> None:
    """Adam7 interlacing is unimplemented, so it must raise, not misdecode."""
    blob = bytearray(_encode([bytes([0, 0])], 1, 1))
    blob[8 + 8 + 12] = 1  # IHDR's interlace byte
    with pytest.raises(ValueError, match="interlaced"):
        png.read_grey(bytes(blob))


def test_rejects_truecolour_by_name() -> None:
    """An unsupported colour type is named in the error, not just numbered."""
    with pytest.raises(ValueError, match="truecolour"):
        png.read_grey(_encode([bytes([0, 0])], 1, 1, colour=png._RGB))  # noqa: SLF001


def test_rejects_an_unknown_row_filter() -> None:
    """A filter byte outside 0-4 is corruption, not something to guess at."""
    with pytest.raises(ValueError, match="row filter"):
        png.read_grey(_encode([bytes([9, 0])], 1, 1))


def test_rejects_a_non_2d_array_on_write() -> None:
    """The writer takes greyscale only; a colour array is a caller mistake."""
    with pytest.raises(ValueError, match="2-D"):
        png.write_grey(np.zeros((2, 2, 3), dtype=np.uint8))
