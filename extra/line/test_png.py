"""Tests for png.py.

Run via: uv run --with pytest pytest test_png.py

png.py replaced Pillow (see the dependency notes in extract.py), so what
needs guarding is that it still reads the checked-in wiki fixtures the way
Pillow did and round-trips what render.py writes.  Pillow is not available
to compare against here, so the fixture expectations below are the values
Pillow produced when the swap was made, recorded as constants.

Beyond that: every row filter the spec defines (the fixtures between them
use 0/1/2/4, but a PNG this reads could legitimately use 3), the sub-byte
bit depths, the colour types (a drawing that has been through an image
editor comes back as RGB), and the rejections -- an unsupported format must
raise rather than decode something plausible-looking but wrong.
"""

from __future__ import annotations

import random
import struct
import zlib
from pathlib import Path

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
    (height, width), ink = expected
    grey = png.read_grey_file(str(FIXTURES / name))
    assert len(grey) == height
    assert {len(row) for row in grey} == {width}
    assert sum(level < 128 for row in grey for level in row) == ink
    # These are 1-bit black-and-white images: nothing in between.
    assert {level for row in grey for level in row} == {0, 255}


@pytest.mark.parametrize("shape", [(1, 1), (3, 7), (64, 65), (200, 133)])
def test_roundtrip_preserves_every_byte(shape: tuple[int, int]) -> None:
    """Writing then reading arbitrary greyscale rows is the identity."""
    height, width = shape
    rng = random.Random(0)
    original = [
        bytearray(rng.randrange(256) for _ in range(width)) for _ in range(height)
    ]
    assert png.read_grey(png.write_grey(original)) == original


def test_roundtrip_through_a_file(tmp_path: Path) -> None:
    """The file-level helpers agree with the in-memory pair."""
    path = tmp_path / "out.png"
    original = [bytearray([0, 128]), bytearray([255, 7])]
    png.write_grey_file(str(path), original)
    assert png.read_grey_file(str(path)) == original


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
    want = [
        bytearray([3, 200, 3, 255]),
        bytearray([200, 3, 100, 0]),
        bytearray([7, 250, 130, 130]),
        bytearray([130, 130, 4, 251]),
    ]
    height, width = len(want), len(want[0])
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            value = want[y][x]
            left = want[y][x - 1] if x else 0
            up = want[y - 1][x] if y else 0
            upleft = want[y - 1][x - 1] if y and x else 0
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
    assert png.read_grey(_encode(rows, width, height)) == want


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
    assert png.read_grey(blob) == [bytearray(expected)]


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
    assert png.read_grey(blob) == [bytearray([255, 0])]


@pytest.mark.parametrize(
    ("colour", "pixel", "expected"),
    [
        # Luma weights are ITU-R 601-2, rounded to nearest as Pillow rounds:
        # (r*19595 + g*38470 + b*7471 + 0x8000) >> 16.
        (png._RGB, [255, 0, 0], 76),  # noqa: SLF001
        (png._RGB, [0, 255, 0], 150),  # noqa: SLF001
        (png._RGB, [0, 0, 255], 29),  # noqa: SLF001
        (png._RGB, [170, 85, 42], 106),  # noqa: SLF001
        # Alpha is dropped, not composited -- the colour reads the same
        # whatever the alpha channel says.
        (png._RGBA, [255, 0, 0, 0], 76),  # noqa: SLF001
        (png._RGBA, [255, 0, 0, 255], 76),  # noqa: SLF001
        (png._GREY_ALPHA, [200, 0], 200),  # noqa: SLF001
        (png._GREY_ALPHA, [200, 255], 200),  # noqa: SLF001
    ],
)
def test_colour_types_reduce_to_grey_as_pillow_does(
    colour: int, pixel: list[int], expected: int
) -> None:
    """Colour and alpha images reduce to the grey level Pillow produces.

    A Line drawing opened and re-saved in an image editor typically comes
    back as RGB even though it is visually black and white, so refusing
    colour would refuse a file the user reasonably considers the same
    drawing.  The expected values here were taken from Pillow's own
    ``convert("L")`` output.
    """
    blob = _encode([bytes([0, *pixel])], 1, 1, colour=colour)
    assert png.read_grey(blob) == [bytearray([expected])]


def test_multi_channel_filters_step_by_a_whole_pixel() -> None:
    """A colour row's Sub filter predicts from the pixel left, not the byte.

    With 3 bytes per pixel the predictor looks back 3 bytes; using 1 would
    decode a plausible-looking but wrong image rather than failing loudly.
    """
    want = [(10, 20, 30), (40, 60, 90), (200, 130, 70)]
    row = bytearray([1])  # filter type: Sub
    for i, (red, green, blue) in enumerate(want):
        prev = want[i - 1] if i else (0, 0, 0)
        row += bytes(
            (channel - prev[j]) & 0xFF for j, channel in enumerate((red, green, blue))
        )
    blob = _encode([bytes(row)], 3, 1, colour=png._RGB)  # noqa: SLF001
    expected = bytearray(
        (r * 19595 + g * 38470 + b * 7471 + 0x8000) >> 16 for r, g, b in want
    )
    assert png.read_grey(blob) == [expected]


def test_rejects_a_sixteen_bit_palette() -> None:
    """Palette indices are at most 8 bits, so 16-bit palette is malformed."""
    with pytest.raises(ValueError, match="palette"):
        png.read_grey(_encode([bytes([0, 0, 0])], 1, 1, depth=16, colour=png._PALETTE))  # noqa: SLF001


def test_rejects_sub_byte_depth_on_a_colour_image() -> None:
    """Sub-byte samples are single-channel only, per the spec."""
    with pytest.raises(ValueError, match="bit depth"):
        png.read_grey(_encode([bytes([0, 0])], 1, 1, depth=4, colour=png._RGB))  # noqa: SLF001


def _adam7_encode(pixels: list[list[int]], width: int, height: int) -> bytes:
    """Encode 8-bit greyscale as an interlaced PNG, filter 0 throughout."""
    raw = bytearray()
    for row0, col0, row_step, col_step in png._ADAM7:  # noqa: SLF001
        cols = list(range(col0, width, col_step))
        rows = list(range(row0, height, row_step))
        if not cols or not rows:
            continue
        for y in rows:
            raw.append(0)
            raw += bytes(pixels[y][x] for x in cols)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, png._GREY, 0, 0, 1)  # noqa: SLF001

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    return (
        png._SIGNATURE  # noqa: SLF001
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw)))
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize(("width", "height"), [(1, 1), (5, 3), (9, 9), (16, 7)])
def test_interlaced_reassembles_to_the_same_image(width: int, height: int) -> None:
    """An Adam7 image decodes to what the same pixels say non-interlaced.

    Adam7 stores seven subsampled passes rather than plain scanlines, each
    with its own dimensions, row filters and row padding.  The sizes here
    include ones smaller than the 8x8 lattice, where whole passes are empty
    -- the case an off-by-one in the pass geometry shows up on first.
    """
    pixels = [[(x * 37 + y * 11) % 256 for x in range(width)] for y in range(height)]
    plain = _encode(
        [bytes([0, *row]) for row in pixels],
        width,
        height,
        colour=png._GREY,  # noqa: SLF001
    )
    interlaced = _adam7_encode(pixels, width, height)
    assert png.read_grey(interlaced) == png.read_grey(plain)
    assert png.read_grey(interlaced) == [bytearray(row) for row in pixels]


def test_sixteen_bit_scales_down_rather_than_clipping() -> None:
    """16-bit samples scale onto 0-255; they are not clipped there.

    This deliberately departs from Pillow, whose ``I;16 -> L`` conversion
    clips: under it every 16-bit value above 255 comes out white, so a
    drawing whose ink is stored as (say) 1000 would decode to a blank page
    with every stroke erased.  The two agree on pure 0 and pure 65535, which
    is what a clean black-and-white drawing actually holds.
    """
    values = [0, 256, 1000, 32768, 60000, 65535]
    row = bytearray([0])
    for value in values:
        row += struct.pack(">H", value)
    blob = _encode([bytes(row)], len(values), 1, depth=16, colour=png._GREY)  # noqa: SLF001
    assert png.read_grey(blob) == [bytearray(v >> 8 for v in values)]


def test_sixteen_bit_colour_reduces_through_luma() -> None:
    """A 16-bit RGB pixel scales per channel, then reduces like any colour."""
    row = bytearray([0])
    for value in (65535, 0, 0):  # pure red at full depth
        row += struct.pack(">H", value)
    blob = _encode([bytes(row)], 1, 1, depth=16, colour=png._RGB)  # noqa: SLF001
    assert png.read_grey(blob) == [bytearray([76])]


def test_rejects_a_non_png() -> None:
    """Bytes that are not a PNG at all are refused up front."""
    with pytest.raises(ValueError, match="signature"):
        png.read_grey(b"not a png at all")


def test_rejects_an_unknown_interlace_method() -> None:
    """Only the spec's two interlace methods exist; anything else is corrupt."""
    blob = bytearray(_encode([bytes([0, 0])], 1, 1))
    blob[8 + 8 + 12] = 7  # IHDR's interlace byte
    with pytest.raises(ValueError, match="interlace method"):
        png.read_grey(bytes(blob))


def test_rejects_an_unknown_colour_type_by_number() -> None:
    """A colour type outside the spec is refused rather than guessed at."""
    with pytest.raises(ValueError, match="colour type 5"):
        png.read_grey(_encode([bytes([0, 0])], 1, 1, colour=5))


def test_rejects_an_unknown_row_filter() -> None:
    """A filter byte outside 0-4 is corruption, not something to guess at."""
    with pytest.raises(ValueError, match="row filter"):
        png.read_grey(_encode([bytes([9, 0])], 1, 1))


def test_rejects_ragged_rows_on_write() -> None:
    """Rows of differing lengths are not an image; the writer must say so."""
    with pytest.raises(ValueError, match="equal-length rows"):
        png.write_grey([bytearray([0, 0]), bytearray([0])])
