"""PNG pixel compatibility, round trips, and corruption checks."""

from __future__ import annotations

import base64
import gzip
import io
import json
import random
import struct
import zlib
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

import esolangs
from esolangs.operations.source import read_png_artifact
from esolangs.raster import png
from tests.support.pick import one
from tests.support.reference import REFERENCE

#: Two wiki images, kept apart from any one language's fixtures so the codec
#: tests outlive the language that drew them.
FIXTURES = Path(__file__).parents[2] / "support/fixtures"

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
        png._SIGNATURE
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
        png._SIGNATURE
        + _chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", 2, 1, 1, png._PALETTE, 0, 0, 0),
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
        (png._RGB, [255, 0, 0], 76),
        (png._RGB, [170, 85, 42], 106),
        # Alpha is dropped, not composited -- the colour reads the same
        # whatever the alpha channel says.
        (png._RGBA, [255, 0, 0, 0], 76),
        (png._GREY_ALPHA, [200, 0], 200),
    ],
)
def test_colour_types_reduce_to_grey_as_pillow_does(
    colour: int, pixel: list[int], expected: int
) -> None:
    """Colour and alpha images reduce to the grey level Pillow produces."""
    blob = _encode([bytes([0, *pixel])], 1, 1, colour=colour)
    assert png.read_grey(blob) == [bytearray([expected])]
    rgb = png.read_rgb(blob)
    if colour in (png._RGB, png._RGBA):
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
    blob = _encode([bytes(row)], 3, 1, colour=png._RGB)
    expected = bytearray(
        (r * 19595 + g * 38470 + b * 7471 + 0x8000) >> 16 for r, g, b in want
    )
    assert png.read_grey(blob) == [expected]


def _adam7_encode(pixels: list[list[int]], width: int, height: int) -> bytes:
    """Encode 8-bit greyscale as an interlaced PNG, filter 0 throughout."""
    raw = bytearray()
    for row0, col0, row_step, col_step in png._ADAM7:
        cols = list(range(col0, width, col_step))
        rows = list(range(row0, height, row_step))
        if not cols or not rows:
            continue
        for y in rows:
            raw.append(0)
            raw += bytes(pixels[y][x] for x in cols)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, png._GREY, 0, 0, 1)

    return (
        png._SIGNATURE
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
        colour=png._GREY,
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
    blob = _encode([bytes(row)], len(values), 1, depth=16, colour=png._GREY)
    assert png.read_grey(blob) == [bytearray(v >> 8 for v in values)]
    assert png.read_rgb(blob) == [[(v >> 8,) * 3 for v in values]]


def test_sixteen_bit_colour_reduces_through_luma() -> None:
    """A 16-bit RGB pixel scales per channel, then reduces like any colour."""
    row = bytearray([0])
    for value in (65535, 0, 0):  # pure red at full depth
        row += struct.pack(">H", value)
    blob = _encode([bytes(row)], 1, 1, depth=16, colour=png._RGB)
    assert png.read_grey(blob) == [bytearray([76])]
    assert png.read_rgb(blob) == [[(255, 0, 0)]]


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
        png.read_rgb(_encode([bytes([0, 0])], 1, 1, colour=png._PALETTE))
    with pytest.raises(ValueError, match="no PLTE"):
        png.read_grey(_encode([bytes([0, 0])], 1, 1, colour=png._PALETTE))


def test_rgb_rejects_an_index_outside_the_palette() -> None:
    blob = (
        png._SIGNATURE
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, png._PALETTE, 0, 0, 0))
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
            png._SIGNATURE
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, png._PALETTE, 0, 0, 0))
            + _chunk(b"PLTE", plte)
            + _chunk(b"IDAT", zlib.compress(bytes([0, 0])))
            + _chunk(b"IEND", b"")
        )

    for plte in (b"", bytes([0, 0, 0]) * 257, bytes([0, 0])):
        for reader in (png.read_grey, png.read_rgb):
            with pytest.raises(ValueError, match="malformed PLTE"):
                reader(blob(plte))


def test_a_corrupt_ihdr_dimension_is_refused_before_allocating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A flipped width byte used to OOM-kill the process (SIGKILL)."""
    from PIL import Image

    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", None)
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

    for bad_shape in (42, None, [42]):
        with pytest.raises(esolangs.ProgramError, match="non-empty 2-D RGB"):
            png.write_rgb(bad_shape)


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
        return original_import(name, *args, **kwargs)

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


def test_png_hard_pixel_limit_applies_to_export_and_precedes_inflation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PIL import Image

    raster = esolangs.Raster((((1, 2, 3), (4, 5, 6), (7, 8, 9)),))
    data = raster.to_png()
    api = esolangs.Language(one(source_kind="raster")[0])
    document = api.to_json(raster)
    path = tmp_path / "source.png"
    path.write_bytes(data)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    def unexpected_inflate(*_args: object) -> bytes:
        pytest.fail("oversized PNG reached IDAT inflation")

    monkeypatch.setattr(png, "_inflate_checked", unexpected_inflate)
    match = r"3x1 \(3 pixels\).*2-pixel PNG limit"
    for operation in (
        lambda: esolangs.Raster.from_png(data),
        lambda: api.from_file(path),
        lambda: api.from_json(document),
        raster.to_png,
        lambda: png.write_grey([bytearray(3)]),
        lambda: api.to_json(raster),
        lambda: api.to_file(raster, path),
    ):
        with pytest.raises(esolangs.ProgramError, match=match):
            operation()
    assert path.read_bytes() == data
    assert Image.MAX_IMAGE_PIXELS == 1


def test_png_allows_exact_hard_limit_and_keeps_pillow_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PIL import Image

    raster = esolangs.Raster((((1, 2, 3), (4, 5, 6)),))
    ordinary = raster.to_png()
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)
    assert raster.to_png() == ordinary
    with pytest.warns(Image.DecompressionBombWarning) as warnings:
        assert esolangs.Raster.from_png(ordinary) == raster
    assert len(warnings) == 1

    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", None)
    assert esolangs.Raster.from_png(raster.to_png()) == raster
    assert Image.MAX_IMAGE_PIXELS is None


def test_png_rejects_missing_compressed_checksum() -> None:
    blob = _encode([bytes(4)], 1, 1, colour=2)
    chunks = bytearray(blob[:8])
    for kind, body in png._chunks(blob):
        chunks.extend(_chunk(kind, body[:-1] if kind == b"IDAT" else body))
    with pytest.raises(ValueError, match="truncated PNG compressed stream"):
        png.read_rgb(bytes(chunks))


def test_png_datastream_requires_an_empty_iend() -> None:
    blob = png.write_grey([bytearray([0])])
    with pytest.raises(esolangs.ProgramError, match="no complete IEND"):
        esolangs.Raster.from_png(blob[:-12])
    with pytest.raises(esolangs.ProgramError, match="IEND chunk must be empty"):
        esolangs.Raster.from_png(blob[:-12] + _chunk(b"IEND", b"x"))


def test_png_final_idat_may_have_unused_bytes() -> None:
    image = png.write_grey([bytearray([0])])
    data = b"".join(
        _chunk(kind, body + b"\x00extra" if kind == b"IDAT" else body)
        for kind, body in png._chunks(image)
    )
    assert esolangs.Raster.from_png(png._SIGNATURE + data) == esolangs.Raster.from_png(
        image
    )


@pytest.mark.parametrize("language", one(source_kind="raster"))
def test_png_metadata_stops_at_iend(language: str, tmp_path: Path) -> None:
    expected = esolangs.Language(language).from_source(esolangs.Raster((((0, 0, 0),),)))
    path = tmp_path / "program"
    path.write_bytes(expected.source.to_png() + _chunk(b"esOL", b'{"version":9}'))
    assert esolangs.from_file(language, path) == expected


@pytest.mark.parametrize(
    "suffix",
    [
        b"",
        b"tail",
        b"foreign attached bytes",
        b"foreign attached bytes" + _chunk(b"IEND", b""),
    ],
    ids=["ordinary", "short-tail", "long-tail", "trailing-iend"],
)
def test_png_metadata_writer_preserves_data_after_iend(
    suffix: bytes, tmp_path: Path
) -> None:
    api = esolangs.Language(one(source_kind="raster")[0])
    pixels = esolangs.Raster((((1, 2, 3),),))
    raw = pixels.to_png()
    metadata = {
        "version": 1,
        "language": api.name,
        "settings": None,
        "scale": None,
        "input_arity": 1,
    }
    body = json.dumps(metadata, separators=(",", ":")).encode("ascii")
    expected = raw[:-12] + _chunk(b"esOL", body) + raw[-12:] + suffix
    path = tmp_path / "program.png"
    path.write_bytes(raw + suffix)
    assert api.from_file(path) == api.from_source(pixels)

    for tagged in (
        png.write_metadata(raw + suffix, metadata),
        png.attach_source_metadata(raw + suffix, api.name, None, None, input_arity=1),
    ):
        assert tagged == expected
        path.write_bytes(tagged)
        assert api.from_file(path) == esolangs.ProgramArtifact(
            pixels, api.name, input_arity=1
        )


@pytest.mark.parametrize("language", one(source_kind="raster"))
def test_named_png_damage_and_portable_wrapper_keep_repair_notes(
    language: str, tmp_path: Path
) -> None:
    api = esolangs.Language(language)
    pixels = esolangs.Raster((((1, 2, 3),),))
    good = pixels.to_png()
    truncated = good[:-12]
    path = tmp_path / "source.png"
    path.write_bytes(truncated)
    with pytest.raises(esolangs.ProgramError, match="no complete IEND") as native:
        api.from_file(path)
    assert str(path) in str(native.value)
    assert native.value.__notes__

    value = json.loads(api.to_json(pixels))
    value["source"] = base64.b64encode(truncated).decode("ascii")
    with pytest.raises(esolangs.ProgramError, match="no complete IEND") as portable:
        api.from_json(json.dumps(value))
    assert portable.value.__notes__ == native.value.__notes__

    path.write_bytes(good)
    assert api.from_file(path).source == pixels
    with pytest.raises(
        esolangs.ProgramError, match="requires text source"
    ) as wrong_kind:
        esolangs.from_file(REFERENCE, path)
    assert str(path) in str(wrong_kind.value)


@pytest.mark.parametrize("language", one(source_kind="raster"))
def test_png_source_kind_checked_before_dependency(
    language, tmp_path, monkeypatch
) -> None:
    api = esolangs.Language(language)
    generated = api.generate("01")
    image = generated.source.to_png()
    path = tmp_path / "program"
    path.write_bytes(image)
    portable = json.loads(api.to_json(image))
    for record in (api.from_file(path), api.from_json(json.dumps(portable))):
        assert tuple(record.evaluate((bit,)).answer for bit in (0, 1)) == ("0", "1")
    portable["language"] = REFERENCE
    monkeypatch.setattr(png, "Image", None)
    with pytest.raises(esolangs.MissingDependencyError):
        esolangs.from_file(language, path)
    for load in (
        lambda: esolangs.from_file(REFERENCE, path),
        lambda: esolangs.from_source(REFERENCE, generated.source),
        lambda: esolangs.prepare(REFERENCE, generated.source),
        lambda: esolangs.prepare(REFERENCE, image),
        lambda: esolangs.to_json(REFERENCE, image),
        lambda: esolangs.from_json(REFERENCE, json.dumps(portable)),
    ):
        with pytest.raises(
            esolangs.ProgramError, match="requires text source"
        ) as refused:
            load()
        assert refused.value.__notes__ == [
            "hint: use text source or select the language that reads the raster"
        ]


@pytest.mark.parametrize("language", one(source_kind="raster"))
def test_raster_language_names_gzip_before_decoding(
    language: str, tmp_path: Path, monkeypatch
) -> None:
    api = esolangs.Language(language)
    gzip_bytes = gzip.compress(b"+.", mtime=0)
    compressed = esolangs.CompressedText(gzip_bytes)
    text = esolangs.Language(REFERENCE)
    assert text.run(compressed).output == "\x01"
    document = json.loads(text.to_json(compressed))
    document["language"] = language
    path = tmp_path / "program.gz"
    path.write_bytes(gzip_bytes)
    message = "requires raster source, but the program is gzip text"

    def unexpected_decode(*_args):
        pytest.fail("the wrong source kind reached decoding")

    monkeypatch.setattr(esolangs.CompressedText, "chunks", unexpected_decode)
    monkeypatch.setattr(png, "read_metadata", unexpected_decode)
    for load in (
        lambda: api.prepare(gzip_bytes),
        lambda: api.to_json(io.BytesIO(gzip_bytes)),
        lambda: api.prepare(compressed),
        lambda: api.from_source(compressed),
        lambda: api.run(esolangs.ProgramArtifact(compressed, language)),
    ):
        with pytest.raises(esolangs.ProgramError, match=message) as refused:
            load()
        assert any("use a PNG" in note for note in refused.value.__notes__)
    with pytest.raises(esolangs.ProgramError, match=message) as native:
        api.from_file(path)
    assert str(path) in str(native.value)
    assert any("use a PNG" in note for note in native.value.__notes__)
    with pytest.raises(esolangs.ProgramError, match=message) as portable:
        api.from_json(json.dumps(document))
    assert portable.value.__notes__ == native.value.__notes__


def test_png_rejects_dimensions_beyond_platform_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PIL import Image

    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", None)
    blob = _encode([bytes(4)], 0xFFFFFFFF, 0xFFFFFFFF, depth=16, colour=6)
    with pytest.raises(ValueError, match="IHDR"):
        png.read_rgb(blob)


#: (call, argument, what the refusal says) for one-call refusals.
_REFUSED = {
    # Palette indices are at most 8 bits, so 16-bit palette is malformed.
    "rejects_a_sixteen_bit_palette": (
        png.read_grey,
        _encode([bytes([0, 0, 0])], 1, 1, depth=16, colour=png._PALETTE),
        "palette",
    ),
    # Sub-byte samples are single-channel only, per the spec.
    "rejects_sub_byte_depth_on_a_colour_image": (
        png.read_grey,
        _encode([bytes([0, 0])], 1, 1, depth=4, colour=png._RGB),
        "bit depth",
    ),
    "rejects_a_non_png": (png.read_grey, b"not a png at all", "signature"),
    "rejects_an_unknown_colour_type_by_number": (
        png.read_grey,
        _encode([bytes([0, 0])], 1, 1, colour=5),
        "colour type 5",
    ),
    "rejects_a_missing_header": (png.read_rgb, png._SIGNATURE, "no IHDR"),
    "rejects_a_truncated_chunk": (
        png.read_rgb,
        png._SIGNATURE + struct.pack(">I", 4) + b"IHDR" + b"x",
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


@pytest.mark.medium
def test_text_import_defers_pillow_until_png_io() -> None:
    import subprocess
    import sys

    source = """
import sys
import esolangs
assert 'PIL.Image' not in sys.modules
raster = esolangs.Raster((((1, 2, 3),),))
data = raster.to_png()
assert 'PIL.Image' in sys.modules
assert esolangs.Raster.from_png(data).rows == raster.rows
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "fields",
    [
        {"language": True},
        {"scale": 0},
        {"scale": True},
        {"settings": []},
        {"settings": {"unknown": "value"}},
        {"settings": {"cell_modulus": {"integer": "bad-value"}}},
        {
            "language": one(source_kind="raster", dialect_settings={})[0],
            "settings": {"cell_modulus": 2},
        },
    ],
)
def test_bad_source_metadata_is_a_program_error(fields) -> None:
    from esolangs.exceptions import ProgramError

    data = png.write_rgb((((1, 2, 3),),))
    data = png.write_metadata(
        data, {"version": 1, "language": None, "scale": None, "settings": None} | fields
    )
    with pytest.raises(ProgramError, match="not a readable PNG"):
        read_png_artifact(one(source_kind="raster")[0], data)


def test_unsupported_metadata_versions_are_rejected() -> None:
    from esolangs import ProgramError

    data = png.write_rgb((((1, 2, 3),),))
    tagged = png.write_metadata(data, {"version": 2, "language": True})
    language = one(source_kind="raster")[0]
    with pytest.raises(ProgramError, match="unsupported esolangs PNG metadata version"):
        read_png_artifact(language, tagged)
    restored = read_png_artifact(language, data)
    assert restored.source.rows == (((1, 2, 3),),)
    assert restored.language == language
    assert not hasattr(restored.source, "language")
    versions = (None, True, False, 0, -1, 1.0, 2.0, "1", [], {})
    for fields in ({}, *({"version": v} for v in versions)):
        with pytest.raises(ProgramError, match="invalid esolangs PNG metadata version"):
            read_png_artifact(
                one(source_kind="raster")[0], png.write_metadata(data, fields)
            )


def test_duplicate_source_metadata_is_refused() -> None:
    from esolangs.exceptions import ProgramError

    data = png.write_rgb((((1, 2, 3),),))
    data = png.write_metadata(data, {"version": 1})
    data = png.write_metadata(data, {"version": 1})
    with pytest.raises(ProgramError, match="duplicate"):
        read_png_artifact(one(source_kind="raster")[0], data)
    with pytest.raises(ProgramError, match="duplicate"):
        png.attach_source_metadata(data, None, None, 1)
    for body in (
        b'{"version":1,"version":1}',
        b'{"version":1,"settings":{"cell_modulus":2,"cell_modulus":2}}',
        b'{"version":1,"input_arity":1,"input_arity":2}',
    ):
        plain = png.write_rgb((((1, 2, 3),),))
        duplicate = plain[:-12] + _chunk(b"esOL", body) + plain[-12:]
        with pytest.raises(ProgramError, match="duplicate field"):
            read_png_artifact(one(source_kind="raster")[0], duplicate)


@pytest.mark.parametrize("body", [b"[]", b"broken-json", b"x" * 16_385])
def test_malformed_source_metadata_is_refused(body) -> None:
    from esolangs.exceptions import ProgramError

    data = png.write_rgb((((1, 2, 3),),))
    data = data[:-12] + _chunk(b"esOL", body) + data[-12:]
    with pytest.raises(ProgramError, match="not a readable PNG"):
        read_png_artifact(one(source_kind="raster")[0], data)


@pytest.mark.parametrize(
    "encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-32"]
)
def test_source_metadata_bytes_require_utf8(encoding: str, tmp_path: Path) -> None:
    api = esolangs.Language(one(source_kind="raster")[0])
    pixels = esolangs.Raster((((1, 2, 3),),))
    raw = pixels.to_png()
    body = '{"version":1,"language":null,"settings":null,"scale":4}'.encode(encoding)
    data = raw[:-12] + _chunk(b"esOL", body) + raw[-12:]
    path = tmp_path / "source.png"
    path.write_bytes(data)
    portable = json.loads(api.to_json(pixels))
    portable["source"] = base64.b64encode(data).decode("ascii")
    document = json.dumps(portable)

    assert esolangs.Raster.from_png(data) == pixels
    if encoding.startswith("utf-8"):
        assert api.from_file(path) == api.from_json(document)
        assert api.from_file(path).scale == 4
    else:
        with pytest.raises(esolangs.ProgramError, match="not a readable PNG"):
            api.from_file(path)
        with pytest.raises(esolangs.ProgramError, match="not a readable PNG"):
            api.from_json(document)


@pytest.mark.parametrize("token", ["1e5000", "NaN", "Infinity", "-Infinity"])
def test_source_metadata_ignores_only_valid_json_extensions(
    token: str, tmp_path: Path
) -> None:
    api = esolangs.Language(one(source_kind="raster")[0])
    pixels = esolangs.Raster((((1, 2, 3),),))
    raw = pixels.to_png()
    body = (
        '{"version":1,"language":null,"settings":null,"scale":null,"extra":'
        + token
        + "}"
    ).encode("ascii")
    data = raw[:-12] + _chunk(b"esOL", body) + raw[-12:]
    path = tmp_path / "source.png"
    path.write_bytes(data)
    portable = json.loads(api.to_json(pixels))
    portable["source"] = base64.b64encode(data).decode("ascii")
    document = json.dumps(portable)

    assert esolangs.Raster.from_png(data) == pixels
    if token == "1e5000":
        assert api.from_file(path) == api.from_json(document) == api.from_source(pixels)
        tagged = png.attach_source_metadata(data, api.name, None, None, input_arity=1)
        assert b"1e5000" in tagged
        path.write_bytes(tagged)
        assert api.from_file(path) == replace(api.from_source(pixels), input_arity=1)
    else:
        for load in (lambda: api.from_file(path), lambda: api.from_json(document)):
            with pytest.raises(
                esolangs.ProgramError, match=f"invalid JSON constant {token}"
            ):
                load()


def test_metadata_writer_bounds_chunk_size() -> None:
    data = png.write_rgb((((1, 2, 3),),))
    with pytest.raises(ValueError, match="oversized"):
        png.write_metadata(data, {"version": 1, "extra": "x" * 16_384})


def test_png_operations_use_stored_bytes() -> None:
    first = (((1, 2, 3),),)
    second = (((9, 8, 7),),)
    raw = png.write_rgb(first)
    other = png.write_rgb(second)
    metadata = {"version": 1, "input_arity": 1}
    alternate = {"version": 1, "input_arity": 2}
    tagged = png.write_metadata(raw, metadata)

    class AlternateBytes(bytes):
        def __bytes__(self):
            return substitute

        def __buffer__(self, _flags):
            return memoryview(substitute)

        def __getitem__(self, key):
            return substitute[key]

    substitute = png.write_metadata(other, alternate)
    shadowed = AlternateBytes(tagged)
    assert png.read_metadata(substitute) == alternate
    assert png.read_metadata(shadowed) == metadata
    assert png.read_rgb(shadowed) == [[(1, 2, 3)]]
    assert png.read_grey(shadowed) == png.read_grey(raw)
    damaged = AlternateBytes(tagged[:-1])
    with pytest.raises(ValueError, match="truncated IEND chunk CRC"):
        png.read_metadata(damaged)
    with pytest.raises(ValueError, match="truncated IEND chunk CRC"):
        png.write_metadata(damaged, metadata)

    substitute = other
    assert png.attach_source_metadata(raw, None, None, None) is raw
    plain = png.attach_source_metadata(AlternateBytes(raw), None, None, None)
    assert type(plain) is bytes
    assert plain == raw
    assert png.write_metadata(AlternateBytes(raw), metadata) == tagged
    assert png.attach_source_metadata(
        AlternateBytes(raw), None, None, None, input_arity=1
    ) == png.attach_source_metadata(raw, None, None, None, input_arity=1)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_metadata_writer_refuses_nonstandard_json_numbers(number: float) -> None:
    data = png.write_rgb((((1, 2, 3),),))
    with pytest.raises(ValueError, match="Out of range float"):
        png.write_metadata(data, {"version": 1, "extra": [number]})
    valid = png.write_metadata(data, {"version": 1, "extra": [1.25]})
    assert png.read_metadata(valid) == {"version": 1, "extra": [1.25]}


@pytest.mark.parametrize("language", one(source_kind="raster"))
def test_png_writer_retains_dialect_owner(language: str, tmp_path: Path) -> None:
    installed = esolangs.Language(language)
    original = installed.catalog.languages[language]
    name, alias = "Scoped Raster", "Private Drawing"
    schema = esolangs.DialectSchema(name, {"ink": (0, 1)}, {"ink": 0})
    runtime = replace(original.runtime, dialect=lambda **_: {}, dialect_schema=schema)
    declaration = replace(
        original,
        name=name,
        runtime=runtime,
        id="",
        aliases=(alias, language),
        backend=None,
    )
    api = esolangs.Catalog([declaration]).bind(name)
    pixels = esolangs.Raster((((1, 2, 3),),))
    raw = pixels.to_png()
    settings = api.settings(ink=1)
    expected = esolangs.ProgramArtifact(pixels, name, settings=settings, scale=1)
    canonical = png.attach_source_metadata(raw, name, settings, 1)
    path = tmp_path / "source.png"

    for owner, options in (
        (None, {}),
        (None, {"catalog": api.catalog}),
        (name, {}),
        ("scoped raster", {}),
        (alias, {"catalog": api.catalog}),
    ):
        tagged = png.attach_source_metadata(raw, owner, settings, 1, **options)
        assert tagged == png.write_source(pixels.rows, owner, settings, 1, **options)
        assert tagged == canonical
        assert png.read_metadata(tagged)["language"] == name
        path.write_bytes(tagged)
        assert api.from_file(path) == expected

    # An installed name can be an alias in a separate catalog. An empty
    # settings object could otherwise be silently accepted by either owner.
    empty = api.settings()
    path.write_bytes(
        png.attach_source_metadata(raw, language, empty, None, catalog=api.catalog)
    )
    assert api.from_file(path).settings == empty
    with pytest.raises(esolangs.ProgramError, match="generated for Scoped Raster"):
        installed.from_file(path)
    other = esolangs.Catalog([replace(original, aliases=(name,))])
    with pytest.raises(esolangs.ArgumentError, match="dialect settings belong to"):
        png.attach_source_metadata(raw, None, settings, 1, catalog=other)
    with pytest.raises(esolangs.ArgumentError, match="catalog must be a Catalog"):
        png.attach_source_metadata(raw, name, settings, 1, catalog=object())

    unscoped = png.attach_source_metadata(raw, alias, None, None)
    assert png.read_metadata(unscoped)["language"] == alias


@pytest.mark.parametrize("language", one(source_kind="raster"))
def test_png_writer_refuses_foreign_dialect_owner(language: str) -> None:
    pixels = esolangs.Raster((((1, 2, 3),),))
    raw = pixels.to_png()
    settings = esolangs.Language(REFERENCE).settings()
    for write in (
        lambda: png.attach_source_metadata(raw, language, settings, 1),
        lambda: png.write_source(pixels.rows, language, settings, 1),
    ):
        with pytest.raises(esolangs.ArgumentError, match="dialect settings belong to"):
            write()


@pytest.mark.parametrize(
    "language", one(source_kind="raster", boolean_generator=True, width_effect="layout")
)
@pytest.mark.parametrize("choices", [{}, {"ink": 1}])
def test_typed_png_writers_validate_dialect_schema(
    language: str, choices: dict[str, int], tmp_path: Path
) -> None:
    api = esolangs.Language(language)
    original = api.catalog.languages[language]
    schema = esolangs.DialectSchema(language, {"ink": (0, 1)}, {"ink": 0})
    runtime = replace(original.runtime, dialect=lambda **_: {}, dialect_schema=schema)
    scoped = esolangs.Catalog([replace(original, runtime=runtime, backend=None)]).bind(
        language
    )
    artifact = api.generate("01")
    assert isinstance(artifact, esolangs.ProgramArtifact)
    pixels = artifact.source
    assert isinstance(pixels, esolangs.Raster)
    raw = pixels.to_png()
    foreign = scoped.settings(**choices)
    installed = api.settings()
    path = tmp_path / "source.png"
    metadata = {"scale": artifact.scale, "input_arity": artifact.input_arity}
    for write in (
        lambda settings, catalog=None: png.attach_source_metadata(
            raw, language, settings, catalog=catalog, **metadata
        ),
        lambda settings, catalog=None: png.write_source(
            pixels.rows, language, settings, catalog=catalog, **metadata
        ),
    ):
        unscoped = write(foreign)
        assert write(foreign, scoped.catalog) == unscoped
        path.write_bytes(unscoped)
        assert scoped.from_file(path) == replace(artifact, settings=foreign)

        with pytest.raises(esolangs.ArgumentError, match="use a different schema"):
            write(foreign, api.catalog)

        tagged = write(installed, api.catalog)
        assert tagged == write(installed)
        path.write_bytes(tagged)
        restored = api.from_file(path)
        assert restored == replace(artifact, settings=installed)
        assert [api.evaluate(restored, [bit]).answer for bit in (0, 1)] == ["0", "1"]


@pytest.mark.parametrize(
    ("scale", "arity", "field"),
    [
        (0, 1, "scale"),
        (True, 1, "scale"),
        (1, -1, "input_arity"),
        (1, True, "input_arity"),
    ],
)
def test_typed_png_writers_reject_invalid_numeric_metadata(scale, arity, field) -> None:
    pixels = esolangs.Raster((((1, 2, 3),),))
    raw = pixels.to_png()
    language = one(source_kind="raster")[0]
    for write in (
        lambda: png.attach_source_metadata(
            raw, language, None, scale, input_arity=arity
        ),
        lambda: png.write_source(pixels.rows, language, None, scale, input_arity=arity),
    ):
        with pytest.raises(
            esolangs.ArgumentError, match=f"{field} must be a positive integer"
        ):
            write()


@pytest.mark.parametrize(
    ("owner", "message"),
    [
        ("", "must be nonblank"),
        (" \t ", "must be nonblank"),
        (True, "must be a string"),
    ],
)
def test_typed_png_writers_require_a_nonblank_owner(owner, message) -> None:
    pixels = esolangs.Raster((((1, 2, 3),),))
    raw = pixels.to_png()
    for write in (
        lambda: png.attach_source_metadata(raw, owner, None, 1),
        lambda: png.write_source(pixels.rows, owner, None, 1),
    ):
        with pytest.raises(esolangs.ArgumentError, match=f"PNG language {message}"):
            write()

    metadata = {"version": 1, "language": owner}
    tagged = png.write_metadata(raw, metadata)
    assert png.read_metadata(tagged) == metadata
    assert esolangs.Raster.from_png(tagged) == pixels
    with pytest.raises(esolangs.ProgramError):
        read_png_artifact(one(source_kind="raster")[0], tagged)


def test_typed_png_writers_reject_untyped_settings() -> None:
    pixels = esolangs.Raster((((1, 2, 3),),))
    raw = pixels.to_png()
    language = one(source_kind="raster")[0]
    settings = object()
    for write in (
        lambda: png.attach_source_metadata(raw, language, settings, 1),
        lambda: png.write_source(pixels.rows, language, settings, 1),
    ):
        with pytest.raises(
            esolangs.ArgumentError, match="settings must be a DialectSettings or None"
        ):
            write()


@pytest.mark.parametrize("language", one(source_kind="raster"))
def test_non_ascii_dialect_metadata_uses_utf8_only_when_needed(
    language, tmp_path
) -> None:
    pixels = esolangs.Raster((((0, 0, 0),),))
    original = esolangs.Language(language).catalog.languages[language]
    note = "é" * 4096
    schema = esolangs.DialectSchema(language, {"note": ("é", note)}, {"note": "é"})
    runtime = replace(original.runtime, dialect=lambda **_: {}, dialect_schema=schema)
    api = esolangs.Catalog([replace(original, runtime=runtime)]).bind(language)
    path = tmp_path / "source.png"
    ordinary = api.from_source(pixels, settings=api.settings(note="é"))
    api.to_file(ordinary, path)
    assert b'"note":"\\u00e9"' in path.read_bytes()

    large = api.from_source(pixels, settings=api.settings(note=note))
    api.to_file(large, path)
    assert note.encode("utf-8") in path.read_bytes()
    assert api.from_file(path) == large
    assert api.from_json(api.to_json(large)) == large


@pytest.mark.parametrize("language", one(source_kind="raster"))
def test_declarations_cannot_persist_surrogate_metadata(language, tmp_path) -> None:
    pixels = esolangs.Raster((((0, 0, 0),),))
    original = esolangs.Language(language).catalog.languages[language]
    schema = esolangs.DialectSchema(language, {"note": ("\ud800",)}, {"note": "\ud800"})
    runtime = replace(original.runtime, dialect=lambda **_: {}, dialect_schema=schema)
    api = esolangs.Catalog([replace(original, runtime=runtime)]).bind(language)
    path = tmp_path / "source.png"
    record = api.from_source(pixels, settings=api.settings(note="\ud800"))
    for save in (lambda: api.to_file(record, path), lambda: api.to_json(record)):
        with pytest.raises(esolangs.ProgramError, match=r"UTF-8.*surrogates"):
            save()
    raw = pixels.to_png()
    path.write_bytes(
        raw[:-12]
        + _chunk(b"esOL", b'{"version":1,"settings":{"note":"\\ud800"}}')
        + raw[-12:]
    )
    with pytest.raises(esolangs.ProgramError, match=r"UTF-8.*surrogates"):
        api.from_file(path)
    assert esolangs.Raster.from_png(path.read_bytes()) == pixels
