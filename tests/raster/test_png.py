"""PNG pixel compatibility, round trips, and corruption checks."""

from __future__ import annotations

import random
import struct
import zlib
from collections.abc import Callable
from pathlib import Path

import pytest

from esolangs.raster import png

FIXTURES = Path(__file__).parents[1] / "fixtures" / "line"

# Shape and ink count (pixels below the 128 threshold extract.py uses) for
# each checked-in fixture, as decoded by Pillow's Image.open().convert("L")
# before png.py replaced it.
FIXTURE_EXPECTATIONS = {
    "addition.png": ((300, 300), 926),
    "multiplication_2x.png": ((1000, 1000), 10896),
}


@pytest.mark.parametrize(("name", "expected"), FIXTURE_EXPECTATIONS.items())
def test_reads_wiki_fixtures_as_pillow_did(
    name: str, expected: tuple[tuple[int, int], int]
) -> None:
    """Each fixture decodes to the shape and ink count Pillow reported."""
    (height, width), ink = expected
    grey = png.read_grey((FIXTURES / name).read_bytes())
    assert len(grey) == height
    assert {len(row) for row in grey} == {width}
    assert sum(level < 128 for row in grey for level in row) == ink
    # These are 1-bit black-and-white images: nothing in between.
    assert {level for row in grey for level in row} == {0, 255}


@pytest.mark.parametrize("shape", [(1, 1), (64, 65)])
def test_roundtrip_preserves_every_byte(shape: tuple[int, int]) -> None:
    """Writing then reading arbitrary greyscale rows is the identity."""
    height, width = shape
    rng = random.Random(0)
    original = [
        bytearray(rng.randrange(256) for _ in range(width)) for _ in range(height)
    ]
    encoded = png.write_grey(original)
    assert png.read_grey(encoded) == original
    assert png.read_rgb(encoded) == [
        [(level, level, level) for level in row] for row in original
    ]


def test_roundtrip_through_a_file(tmp_path: Path) -> None:
    """The file-level helpers agree with the in-memory pair."""
    path = tmp_path / "out.png"
    original = [bytearray([0, 128]), bytearray([255, 7])]
    png.write_grey_file(str(path), original)
    assert png.read_grey(path.read_bytes()) == original


def _chunk(kind: bytes, body: bytes) -> bytes:
    crc = struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return struct.pack(">I", len(body)) + kind + body + crc


def _encode(
    rows: list[bytes], width: int, height: int, depth: int = 8, colour: int = 0
) -> bytes:
    """Build a PNG from already-filtered rows (each prefixed by its filter byte)."""

    ihdr = struct.pack(">IIBBBBB", width, height, depth, colour, 0, 0, 0)
    return (
        png._SIGNATURE  # noqa: SLF001 - building a PNG by hand
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + _chunk(b"IEND", b"")
    )


@pytest.mark.parametrize("filter_type", [0, 1, 2, 3, 4])
def test_every_row_filter_decodes(filter_type: int) -> None:
    """All five spec filters reconstruct the same image."""
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
                row.append((value - _paeth(left, up, upleft)) & 0xFF)
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
    assert png.read_rgb(blob) == [[(value,) * 3 for value in expected]]


def test_palette_is_resolved_through_plte() -> None:
    """A palette image maps indices through PLTE, not straight to greyscale."""

    # Index 0 -> white, index 1 -> black: the fixtures' own palette.
    blob = (
        png._SIGNATURE  # noqa: SLF001 - building a PNG by hand
        + _chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", 2, 1, 1, png._PALETTE, 0, 0, 0),  # noqa: SLF001
        )
        + _chunk(b"PLTE", bytes([255, 255, 255, 0, 0, 0]))
        + _chunk(b"IDAT", zlib.compress(bytes([0, 0b01000000])))
        + _chunk(b"IEND", b"")
    )
    assert png.read_grey(blob) == [bytearray([255, 0])]
    assert png.read_rgb(blob) == [[(255, 255, 255), (0, 0, 0)]]


@pytest.mark.parametrize(
    ("colour", "pixel", "expected"),
    [
        # Luma weights are ITU-R 601-2, rounded to nearest as Pillow rounds:
        # (r*19595 + g*38470 + b*7471 + 0x8000) >> 16.
        (png._RGB, [255, 0, 0], 76),  # noqa: SLF001
        (png._RGB, [170, 85, 42], 106),  # noqa: SLF001
        # Alpha is dropped, not composited -- the colour reads the same
        # whatever the alpha channel says.
        (png._RGBA, [255, 0, 0, 0], 76),  # noqa: SLF001
        (png._GREY_ALPHA, [200, 0], 200),  # noqa: SLF001
    ],
)
def test_colour_types_reduce_to_grey_as_pillow_does(
    colour: int, pixel: list[int], expected: int
) -> None:
    """Colour and alpha images reduce to the grey level Pillow produces."""
    blob = _encode([bytes([0, *pixel])], 1, 1, colour=colour)
    assert png.read_grey(blob) == [bytearray([expected])]
    rgb = png.read_rgb(blob)
    if colour in (png._RGB, png._RGBA):  # noqa: SLF001
        assert rgb == [[tuple(pixel[:3])]]
    else:
        assert rgb == [[(pixel[0],) * 3]]


def test_multi_channel_filters_step_by_a_whole_pixel() -> None:
    """A colour row's Sub filter predicts from the pixel left, not the byte."""
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

    return (
        png._SIGNATURE  # noqa: SLF001
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw)))
        + _chunk(b"IEND", b"")
    )


@pytest.mark.parametrize(("width", "height"), [(1, 1), (16, 7)])
def test_interlaced_reassembles_to_the_same_image(width: int, height: int) -> None:
    """An Adam7 image decodes to what the same pixels say non-interlaced."""
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
    """16-bit samples scale onto 0-255; they are not clipped there."""
    values = [0, 256, 1000, 32768, 60000, 65535]
    row = bytearray([0])
    for value in values:
        row += struct.pack(">H", value)
    blob = _encode([bytes(row)], len(values), 1, depth=16, colour=png._GREY)  # noqa: SLF001
    assert png.read_grey(blob) == [bytearray(v >> 8 for v in values)]
    assert png.read_rgb(blob) == [[(v >> 8,) * 3 for v in values]]


def test_sixteen_bit_colour_reduces_through_luma() -> None:
    """A 16-bit RGB pixel scales per channel, then reduces like any colour."""
    row = bytearray([0])
    for value in (65535, 0, 0):  # pure red at full depth
        row += struct.pack(">H", value)
    blob = _encode([bytes(row)], 1, 1, depth=16, colour=png._RGB)  # noqa: SLF001
    assert png.read_grey(blob) == [bytearray([76])]
    assert png.read_rgb(blob) == [[(255, 0, 0)]]


def test_a_jpeg_is_refused_with_a_usable_message(tmp_path: Path) -> None:
    """A JPEG names itself and the fix, rather than failing on the signature."""
    from esolangs.interpreters.tape_based.line import extract

    path = tmp_path / "drawing.jpg"
    # A JPEG start-of-image plus APP0, which is all the sniff looks at.
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 64)
    with pytest.raises(ValueError, match="is a JPEG") as caught:
        extract.load_binary(str(path))
    assert "PNG" in str(caught.value)


def test_rejects_an_unknown_interlace_method() -> None:
    """Only the spec's two interlace methods exist; anything else is corrupt."""
    blob = bytearray(_encode([bytes([0, 0])], 1, 1))
    blob[8 + 8 + 12] = 7  # IHDR's interlace byte
    _repair_ihdr_crc(blob)
    with pytest.raises(ValueError, match="interlace method"):
        png.read_grey(bytes(blob))


def test_rejects_an_unknown_compression_method() -> None:
    blob = bytearray(_encode([bytes([0, 0])], 1, 1))
    blob[8 + 8 + 10] = 1
    _repair_ihdr_crc(blob)
    with pytest.raises(ValueError, match="compression"):
        png.read_rgb(bytes(blob))


def test_rgb_rejects_an_unknown_depth() -> None:
    with pytest.raises(ValueError, match="bit depth"):
        png.read_rgb(_encode([bytes([0, 0])], 1, 1, depth=3))


def test_rgb_rejects_a_palette_without_entries() -> None:
    with pytest.raises(ValueError, match="no PLTE"):
        png.read_rgb(_encode([bytes([0, 0])], 1, 1, colour=png._PALETTE))  # noqa: SLF001
    with pytest.raises(ValueError, match="no PLTE"):
        png.read_grey(_encode([bytes([0, 0])], 1, 1, colour=png._PALETTE))  # noqa: SLF001


def test_rgb_rejects_an_index_outside_the_palette() -> None:
    blob = (
        png._SIGNATURE  # noqa: SLF001
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, png._PALETTE, 0, 0, 0))  # noqa: SLF001
        + _chunk(b"PLTE", bytes([255, 255, 255]))
        + _chunk(b"IDAT", zlib.compress(bytes([0, 1])))
        + _chunk(b"IEND", b"")
    )
    for reader in (png.read_rgb, png.read_grey):
        with pytest.raises(ValueError, match="outside PLTE"):
            reader(blob)


def test_rejects_a_malformed_palette_length() -> None:
    """A PLTE is 1..256 RGB triples; 257 made only one reader complain."""

    def blob(plte: bytes) -> bytes:
        return (
            png._SIGNATURE  # noqa: SLF001
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, png._PALETTE, 0, 0, 0))  # noqa: SLF001
            + _chunk(b"PLTE", plte)
            + _chunk(b"IDAT", zlib.compress(bytes([0, 0])))
            + _chunk(b"IEND", b"")
        )

    for plte in (b"", bytes([0, 0, 0]) * 257, bytes([0, 0])):
        for reader in (png.read_grey, png.read_rgb):
            with pytest.raises(ValueError, match="malformed PLTE"):
                reader(blob(plte))


def test_a_corrupt_ihdr_dimension_is_refused_before_allocating() -> None:
    """A flipped width byte used to OOM-kill the process (SIGKILL)."""
    data = bytearray(png.write_rgb([[(0, 0, 0)]]))
    data[16] ^= 0x80  # the IHDR width's most significant byte
    _repair_ihdr_crc(data)
    for reader in (png.read_grey, png.read_rgb):
        with pytest.raises(ValueError, match="IHDR is corrupt"):
            reader(bytes(data))


def test_rgb_writer_rejects_empty_ragged_and_invalid_pixels() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        png.write_rgb([])
    with pytest.raises(ValueError, match="non-empty"):
        png.write_rgb([[(0, 0, 0)], []])
    with pytest.raises(ValueError, match="invalid RGB"):
        png.write_rgb([[(0, 0, 256)]])


def _repair_ihdr_crc(blob: bytearray) -> None:
    blob[29:33] = struct.pack(">I", zlib.crc32(blob[12:29]) & 0xFFFFFFFF)


@pytest.mark.parametrize("reader", [png.read_rgb, png.read_grey])
def test_rejects_corrupt_chunk_crc(reader: Callable[[bytes], object]) -> None:
    blob = bytearray(png.write_rgb([[(255, 0, 0), (0, 255, 0)]]))
    blob[19] = 1
    with pytest.raises(ValueError, match="IHDR chunk CRC"):
        reader(bytes(blob))


@pytest.mark.parametrize("reader", [png.read_rgb, png.read_grey])
def test_rejects_incomplete_chunk_crc(reader: Callable[[bytes], object]) -> None:
    blob = png.write_grey([bytearray([0])])
    with pytest.raises(ValueError, match="truncated IEND chunk CRC"):
        reader(blob[:-1])


@pytest.mark.parametrize("reader", [png.read_rgb, png.read_grey])
def test_rejects_surplus_pixel_data(reader: Callable[[bytes], object]) -> None:
    with pytest.raises(ValueError, match="IHDR is corrupt"):
        reader(_encode([bytes([0, 0, 255])], 1, 1))


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    distances = [abs(p - value) for value in (a, b, c)]
    return (a, b, c)[distances.index(min(distances))]


@pytest.mark.parametrize(
    "operation",
    [
        lambda: png.read_rgb(b""),
        lambda: png.read_grey(b""),
        lambda: png.write_rgb([[(0, 0, 0)]]),
        lambda: png.write_grey([bytearray([0])]),
    ],
)
def test_missing_image_extra(
    monkeypatch: pytest.MonkeyPatch, operation: Callable[[], object]
) -> None:
    from esolangs import MissingDependencyError

    monkeypatch.setattr(png, "Image", None)
    with pytest.raises(MissingDependencyError, match=r"esolangs\[image\]"):
        operation()


def test_import_without_pillow(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    import runpy

    from esolangs import MissingDependencyError

    original_import = builtins.__import__

    def without_pillow(name: str, *args: object, **kwargs: object) -> object:
        if name == "PIL":
            raise ModuleNotFoundError("No module named 'PIL'")
        return original_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", without_pillow)
    namespace = runpy.run_path(str(png.__file__))
    with pytest.raises(MissingDependencyError, match=r"esolangs\[image\]"):
        namespace["read_rgb"](b"")


def test_rgb_writer_flushes_repeated_pixels_between_colours_and_at_end() -> None:
    red, black = (255, 0, 0), (0, 0, 0)
    row = (red,) * 19 + (black,) * 7 + (red,) * 11
    assert png.read_rgb(png.write_rgb((row,))) == [list(row)]


@pytest.mark.parametrize("raw_size", [4, 16384])
def test_png_decompression_is_bounded_by_header(monkeypatch, raw_size) -> None:
    original = zlib.decompressobj
    expanded = []

    class BoundedDecoder:
        def __init__(self):
            self.decoder = original()

        def decompress(self, data, max_length):
            result = self.decoder.decompress(data, max_length)
            expanded.append((max_length, len(result)))
            return result

        @property
        def eof(self):
            return self.decoder.eof

    monkeypatch.setattr(png.zlib, "decompressobj", BoundedDecoder)
    blob = _encode([bytes(raw_size)], 1, 1, colour=2)
    if raw_size == 4:
        assert png.read_rgb(blob) == [[(0, 0, 0)]]
    else:
        with pytest.raises(ValueError, match="IHDR"):
            png.read_rgb(blob)
    assert expanded == [(5, min(raw_size, 5))]


def test_png_rejects_missing_compressed_checksum() -> None:
    blob = _encode([bytes(4)], 1, 1, colour=2)
    chunks = bytearray(blob[:8])
    for kind, body in png._chunks(blob):  # noqa: SLF001
        if kind == b"IDAT":
            body = body[:-1]
        chunks.extend(_chunk(kind, body))
    with pytest.raises(ValueError, match="truncated PNG compressed stream"):
        png.read_rgb(bytes(chunks))


def test_png_rejects_dimensions_beyond_platform_size() -> None:
    blob = _encode([bytes(4)], 0xFFFFFFFF, 0xFFFFFFFF, depth=16, colour=6)
    with pytest.raises(ValueError, match="IHDR"):
        png.read_rgb(blob)


#: (call, argument, what the refusal says) for one-call refusals.
_REFUSED = {
    # Palette indices are at most 8 bits, so 16-bit palette is malformed.
    "rejects_a_sixteen_bit_palette": (
        png.read_grey,
        _encode([bytes([0, 0, 0])], 1, 1, depth=16, colour=png._PALETTE),  # noqa: SLF001
        "palette",
    ),
    # Sub-byte samples are single-channel only, per the spec.
    "rejects_sub_byte_depth_on_a_colour_image": (
        png.read_grey,
        _encode([bytes([0, 0])], 1, 1, depth=4, colour=png._RGB),  # noqa: SLF001
        "bit depth",
    ),
    "rejects_a_non_png": (png.read_grey, b"not a png at all", "signature"),
    "rejects_an_unknown_colour_type_by_number": (
        png.read_grey,
        _encode([bytes([0, 0])], 1, 1, colour=5),
        "colour type 5",
    ),
    "rejects_a_missing_header": (png.read_rgb, png._SIGNATURE, "no IHDR"),  # noqa: SLF001
    "rejects_a_truncated_chunk": (
        png.read_rgb,
        png._SIGNATURE + struct.pack(">I", 4) + b"IHDR" + b"x",  # noqa: SLF001
        "truncated IHDR",
    ),
    # A filter byte outside 0-4 is corruption, not something to guess at.
    "rejects_an_unknown_row_filter": (
        png.read_grey,
        _encode([bytes([9, 0])], 1, 1),
        "row filter",
    ),
    "rejects_ragged_rows_on_write": (
        png.write_grey,
        [bytearray([0, 0]), bytearray([0])],
        "equal-length rows",
    ),
}


@pytest.mark.parametrize("case", _REFUSED.values(), ids=list(_REFUSED))
def test_refused(case: tuple[Callable[[object], object], object, str]) -> None:
    call, argument, match = case
    with pytest.raises(ValueError, match=match):
        call(argument)
