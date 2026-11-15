"""Contracts shared by every registered raster language."""

import base64
import json
import os
import sys
import zlib
from array import array
from dataclasses import replace
from importlib.resources import files
from pathlib import Path

import pytest

import esolangs
import esolangs.runtime._execution as _execution_runtime
from esolangs.operations.source import _check_program
from esolangs.raster import Raster, lazy_raster, png
from esolangs.registry import CATALOG, LANGUAGES, SourceKind
from tests.support.dialect_support import integer_setting
from tests.support.evaluation import _evaluate
from tests.support.reference import REFERENCE

RASTER_LANGUAGES = [
    name
    for name, language in LANGUAGES.items()
    if language.runtime.source_kind is SourceKind.RASTER
]


@pytest.mark.medium
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_committed_png_computes_every_row(language: str) -> None:
    examples = esolangs.describe(language).examples
    assert len(examples) == 1
    path = Path(str(files("esolangs") / examples[0]))
    assert _evaluate(language, path, inputs=2) == "0001"


def test_raster_type_has_neutral_ownership() -> None:
    assert Raster.__module__ == "esolangs.raster"
    assert esolangs.Raster is Raster


def test_a_raster_needs_pixels_or_a_materializer() -> None:
    """Both paths absent is a programmer error, not an empty image."""
    with pytest.raises(ValueError, match="pixels or a materializer"):
        Raster(None)


def test_a_raster_hashes_by_pixels() -> None:
    """It is usable as a mapping key, hashed on its immutable pixels."""
    first = Raster((((0, 0, 0),),))
    second = Raster((((0, 0, 0),),))
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


def test_a_raster_language_has_no_template_to_instantiate() -> None:
    """Runnable raster records have no template bindings."""
    with pytest.raises(esolangs.TemplateError):
        esolangs.instantiate(
            RASTER_LANGUAGES[0], esolangs.generate(RASTER_LANGUAGES[0], "01"), [0]
        )


def test_raster_freezes_integer_subclasses_before_validation_and_hashing() -> None:
    class Channel(int):
        __hash__ = None

        def __le__(self, _other):
            return True

        def __ge__(self, _other):
            return True

        def __int__(self):
            return 0

    pixel = (Channel(1), 2, 3)
    raster = Raster(((pixel, pixel),))
    expected = Raster((((1, 2, 3),) * 2,))
    assert raster == expected
    assert hash(raster) == hash(expected)
    assert all(
        type(channel) is int for row in raster.rows for p in row for channel in p
    )
    assert Raster.from_png(raster.to_png()) == expected
    assert png.write_rgb(((pixel, pixel),)) == expected.to_png()
    for invalid in (Channel(999), True, 1.0):
        rows = (((invalid, 2, 3),),)
        with pytest.raises(esolangs.ProgramError, match="RGB triples"):
            Raster(rows)
        with pytest.raises(esolangs.ProgramError, match="invalid RGB"):
            png.write_rgb(rows)
        with pytest.raises(esolangs.ProgramError, match="invalid RGB"):
            png.write_source(rows, None, None, 1)


def test_raster_png_refuses_released_input_buffers() -> None:
    buffer = memoryview(b"")
    buffer.release()
    with pytest.raises(esolangs.ArgumentError, match="PNG data"):
        Raster.from_png(buffer)


def test_raster_png_uses_backing_bytearrays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = Raster((((1, 2, 3),),))
    raw = expected.to_png()
    other = Raster((((9, 8, 7),),))
    substitute = other.to_png()

    class AlternateBytes(bytearray):
        def __bytes__(self):
            return substitute

        def __buffer__(self, _flags):
            return memoryview(substitute)

    assert Raster.from_png(bytearray(raw)) == expected
    assert Raster.from_png(substitute) == other
    assert Raster.from_png(AlternateBytes(raw)) == expected

    class AlternateRow(bytearray):
        def __len__(self):
            return 1

        def __buffer__(self, _flags):
            return memoryview(b"\x00")

    class AlternateRows(list):
        def __iter__(self):
            return iter([bytearray([0])])

        def __getitem__(self, _index):
            return bytearray([0])

    grey = [bytearray([7, 31]), bytearray([53, 89])]
    overridden = AlternateRows([AlternateRow(row) for row in grey])
    encoded = png.write_grey(grey)
    assert png.write_grey(overridden) == encoded
    destination = tmp_path / "greyscale.png"
    png.write_grey_file(str(destination), overridden)
    assert destination.read_bytes() == encoded
    assert png.read_grey(encoded) == grey
    assert Raster.from_png(encoded).rows == (
        ((7, 7, 7), (31, 31, 31)),
        ((53, 53, 53), (89, 89, 89)),
    )
    buffer = array("H", [0x1122, 0x3344])
    levels = bytearray(buffer.tobytes())
    for row in (buffer, memoryview(buffer)):
        assert png.write_grey([row]) == png.write_grey([levels])

    class Once:
        def __init__(self, samples: memoryview) -> None:
            self.samples = samples
            self.acquired = self.released = 0

        def __buffer__(self, _flags: int) -> memoryview:
            self.acquired += 1
            if self.acquired > 1:
                raise BufferError("pixel buffer already acquired")
            return self.samples

        def __release_buffer__(self, _view: memoryview) -> None:
            self.released += 1

    shared = Once(memoryview(levels))
    assert png.write_grey([shared, shared]) == png.write_grey([levels, levels])
    assert shared.acquired == shared.released == 1
    strided = memoryview(levels)[::2]
    rejected = Once(strided)
    with pytest.raises(TypeError, match="bytes-like"):
        png.write_grey([rejected])
    assert rejected.acquired == rejected.released == 1
    assert strided.tobytes() == levels[::2]
    first, short, unread = (
        Once(memoryview(row)) for row in (levels, levels[:1], levels)
    )
    with pytest.raises(ValueError, match="equal-length rows"):
        png.write_grey([first, short, unread])
    assert first.acquired == first.released == short.acquired == short.released == 1
    assert unread.acquired == unread.released == 0

    class ResizeOnRead(Once):
        def __buffer__(self, flags: int) -> memoryview:
            widened.append(99)
            narrowed.pop()
            return super().__buffer__(flags)

    widened, narrowed = map(bytearray, grey)
    source = ResizeOnRead(memoryview(grey[0]))
    with pytest.raises(ValueError, match="greyscale row width changed"):
        png.write_grey([widened, narrowed, source])
    assert source.acquired == source.released == 1
    assert widened.pop() == 99
    narrowed.append(grey[1][-1])
    assert [widened, narrowed] == grey

    relocated = tmp_path / "other"
    relocated.mkdir()
    unrelated = relocated / destination.name
    unrelated.write_bytes(b"unrelated")

    class MovingRow(Once):
        def __buffer__(self, flags: int) -> memoryview:
            os.chdir(relocated)
            return super().__buffer__(flags)

    class MovingPath(os.PathLike[str]):
        calls = 0

        def __fspath__(self) -> str:
            self.calls += 1
            os.chdir(relocated)
            return destination.name

    for path in (destination.name, str(destination)):
        monkeypatch.chdir(tmp_path)
        destination.write_bytes(b"old")
        moving = MovingRow(memoryview(grey[0]))
        png.write_grey_file(path, [moving, grey[1]])
        assert destination.read_bytes() == encoded
        assert unrelated.read_bytes() == b"unrelated"
        assert moving.acquired == moving.released == 1
    monkeypatch.chdir(tmp_path)
    destination.write_bytes(b"old")
    provider = MovingPath()
    with pytest.raises(ValueError, match="equal-length rows"):
        png.write_grey_file(provider, [])
    assert provider.calls == 0
    png.write_grey_file(provider, grey)
    assert provider.calls == 1
    assert destination.read_bytes() == encoded
    assert unrelated.read_bytes() == b"unrelated"

    class ClaimedBytes:
        probes = 0

        @property
        def __class__(self) -> type:
            self.probes += 1
            return bytes

    false_buffer = ClaimedBytes()
    for decode in (Raster.from_png, png.read_rgb, png.read_metadata):
        with pytest.raises(esolangs.ArgumentError, match="PNG data must be bytes"):
            decode(false_buffer)
    assert false_buffer.probes == 0


def test_raster_freezes_backing_tuples_at_each_level() -> None:
    class AlternateTuple(tuple):
        def __new__(cls, values, substitute):
            value = super().__new__(cls, values)
            value.substitute = substitute
            return value

        def __iter__(self):
            return iter(self.substitute)

        def __len__(self):
            return len(self.substitute) + 1

        def __getitem__(self, index):
            return self.substitute[index]

    pixel = (1, 2, 3)
    substitute = (9, 8, 7)
    row = (pixel,)
    rows = (row,)
    expected = Raster(rows)
    for supplied in (
        ((AlternateTuple(pixel, substitute),),),
        (AlternateTuple(row, (substitute,)),),
        AlternateTuple(rows, ((substitute,),)),
    ):
        stored = Raster(supplied)
        assert stored == expected
        assert Raster.from_png(stored.to_png()) == expected
        assert png.write_rgb(supplied) == expected.to_png()
        assert png.write_source(supplied, None, None, 1) == png.write_source(
            rows, None, None, 1
        )

    class ResizeOnMeasure(list):
        def __len__(self) -> int:
            widened.append(pixel)
            narrowed.pop()
            return list.__len__(self)

    widened, narrowed = [pixel], [substitute]
    with pytest.raises(ValueError, match="RGB row width changed"):
        png.write_rgb([widened, narrowed, ResizeOnMeasure([pixel])])
    assert (len(widened), len(narrowed)) == (2, 0)

    class ExtraRow(list):
        def __iter__(self):
            yield from list.__iter__(self)
            yield row

    with pytest.raises(ValueError, match="RGB row count changed"):
        png.write_rgb(ExtraRow([row]))


@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_every_raster_language_generates_shared_source(language: str) -> None:
    program = esolangs.generate(language, "01")
    assert isinstance(program.source, Raster)
    assert program.source.rows
    assert program.source.rows[0]
    assert esolangs.describe(language).source_kind == "raster"
    assert esolangs.run(language, program, stdin="1\n").output == "1"


@pytest.mark.parametrize("language", RASTER_LANGUAGES)
@pytest.mark.parametrize("truth_table", ["0", "1"])
def test_every_raster_generator_rejects_zero_inputs(
    language: str, truth_table: str
) -> None:
    with pytest.raises(esolangs.TruthTableError, match="needs at least one input"):
        esolangs.generate(language, truth_table)


@pytest.mark.slow
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_every_raster_language_runs_its_png(language: str, tmp_path: Path) -> None:
    program = esolangs.generate(language, "01")
    assert isinstance(program.source, Raster)
    path = tmp_path / f"{language.lower()}.png"
    esolangs.to_file(language, program, path)
    assert esolangs.run(language, path, stdin="0\n").output == "0"


@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_a_malformed_png_is_a_program_error(language: str, tmp_path: Path) -> None:
    """Corrupt bytes escaped the package as zlib/struct/Index/MemoryError."""
    truncated = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 4
    assert issubclass(esolangs.ProgramError, ValueError)
    with pytest.raises(esolangs.ProgramError):
        Raster.from_png(truncated)
    path = tmp_path / f"bad-{language.lower()}.png"
    path.write_bytes(truncated)
    with pytest.raises(esolangs.ProgramError):
        _check_program(language, path)

    raster = Raster((((7, 31, 53),),))
    encoded = raster.to_png()
    chunks = dict(png._chunks(encoded))
    header, compressed = chunks[b"IHDR"], chunks[b"IDAT"]

    def encode_chunk(kind: bytes, body: bytes) -> bytes:
        chunk = kind + body
        return (
            len(body).to_bytes(4, "big") + chunk + zlib.crc32(chunk).to_bytes(4, "big")
        )

    invalid_checksum = compressed[:-1] + bytes([compressed[-1] ^ 1])
    for invalid_kind, invalid_body, message in (
        (b"IHDR", header[:-1], "IHDR must be 13 bytes"),
        (b"IHDR", header + b"\0", "IHDR must be 13 bytes"),
        (b"IDAT", invalid_checksum, "invalid PNG compressed stream"),
    ):
        malformed = encoded[:8] + b"".join(
            encode_chunk(kind, invalid_body if kind == invalid_kind else body)
            for kind, body in chunks.items()
        )
        for read in (png.read_rgb, png.read_grey, Raster.from_png):
            with pytest.raises(ValueError, match=message) as caught:
                read(malformed)
            assert "re-export" in caught.value.__notes__[0]
        path.write_bytes(malformed)
        with pytest.raises(esolangs.ProgramError, match=message) as caught:
            esolangs.from_file(language, path)
        assert "re-export" in caught.value.__notes__[0]
    path.write_bytes(encoded)
    assert esolangs.from_file(language, path).source == raster


def test_raster_detaches_mutable_pixels() -> None:
    pixels = [[[0, 0, 0]]]
    raster = Raster(pixels)
    before = hash(raster)
    pixels[0][0][0] = 255
    assert raster.rows == (((0, 0, 0),),)
    assert hash(raster) == before
    assert Raster.from_png(raster.to_png()) == raster


def test_raster_refuses_invalid_channel_types() -> None:
    for channel in (1.5, True, "1", None, -1, 256):
        with pytest.raises(ValueError, match="8-bit RGB"):
            Raster((((channel, 0, 0),),))


def test_lazy_raster_freezes_once_on_access() -> None:
    pixels = [[[0, 0, 0]]]
    calls = 0

    def materialize() -> list[list[list[int]]]:
        nonlocal calls
        calls += 1
        return pixels

    raster = lazy_raster(materialize)
    assert calls == 0
    assert raster.rows == (((0, 0, 0),),)
    pixels[0][0][0] = 255
    assert raster.rows == (((0, 0, 0),),)
    assert calls == 1
    assert hash(raster) == hash(Raster((((0, 0, 0),),)))


def test_lazy_raster_does_not_cache_invalid_pixels() -> None:
    pixels = [[[256, 0, 0]]]
    raster = lazy_raster(lambda: pixels)
    with pytest.raises(ValueError, match="8-bit RGB"):
        _ = raster.rows
    pixels[0][0][0] = 0
    assert raster.rows == (((0, 0, 0),),)


@pytest.mark.medium
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_bounded_raster_run_preserves_explicit_scale(language: str, native_png) -> None:
    from esolangs.debugger import make_debugger
    from esolangs.vm import make_vm

    source = esolangs.generate(language, "01", scale=2)
    assert isinstance(source.source, Raster)
    source = esolangs.Language(language).from_source(
        Raster.from_png(native_png(source))
    )
    assert (
        esolangs.run(
            language,
            source,
            stdin="1\n",
            scale=2,
            limits=esolangs.ExecutionLimits(max_steps=1000),
        ).output
        == "1"
    )
    vm = make_vm(language, source, stdin="0\n", scale=2)
    while not vm.halted:
        vm.step()
    assert vm.output == "0"
    debugger = make_debugger(language, source, stdin="1\n", scale=2)
    assert debugger.run(limits=esolangs.ExecutionLimits(max_steps=1000)) == "halted"
    assert debugger.output == "1"
    assert esolangs.describe(language).state_model in {"tape", "stack"}


@pytest.mark.parametrize("channel", [True, 1.0])
def test_palette_validation_does_not_confuse_equal_channel_types(
    channel: object,
) -> None:
    valid = (1, 0, 0)
    with pytest.raises(ValueError, match="RGB"):
        Raster(((valid, (channel, 0, 0)),))


@pytest.mark.parametrize("builder_name", ["make_vm", "make_debugger"])
def test_text_step_builders_refuse_raster_scale(builder_name: str) -> None:
    import esolangs.debugger as debugger

    builder = getattr(debugger, builder_name)
    with pytest.raises(esolangs.ArgumentError, match="only supported for raster"):
        builder(REFERENCE, "+", scale=2)
    with pytest.raises(esolangs.ArgumentError):
        builder(REFERENCE, "+", scale=0)


def test_repeated_tuple_rows_with_mutable_pixels_are_revalidated() -> None:
    pixel = [0, 0, 0]
    row = (pixel,)

    def rows():
        yield row
        pixel[0] = 255
        yield row

    assert Raster(rows()).rows == (((0, 0, 0),), ((255, 0, 0),))


def test_repeated_tuple_rows_do_not_hide_an_invalid_mutation() -> None:
    pixel = [0, 0, 0]
    row = (pixel,)

    def rows():
        yield row
        pixel[0] = True
        yield row

    with pytest.raises(ValueError, match="RGB"):
        Raster(rows())


@pytest.mark.parametrize("rows", [((None,),), 5, None, ((5,),), ()])
def test_raster_refuses_with_a_program_error(rows: object) -> None:
    """A raw TypeError or ValueError escaped ``except EsolangError``."""
    with pytest.raises(esolangs.ProgramError):
        Raster(rows)  # type: ignore[arg-type]


def test_raster_repr_names_its_size() -> None:
    assert repr(Raster(((((1, 2, 3),) * 2),))) == ("Raster(2x1)")


def test_an_oversized_upscale_is_refused_before_rendering() -> None:
    """``scale=99999`` was OOM-killed with no message; generate refuses it now."""
    for language in RASTER_LANGUAGES:
        with pytest.raises(esolangs.ArgumentError, match="pixel limit"):
            esolangs.generate(language, "0110", scale=10**4)


@pytest.mark.medium
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
@pytest.mark.parametrize("scale", [1, 2])
def test_png_metadata_round_trip_executes(language, scale, native_png) -> None:
    settings = esolangs.Language(language).settings()
    source = esolangs.generate(language, "0110", scale=scale, settings=settings)
    restored = _check_program(language, native_png(source))
    assert restored.source.rows == source.source.rows
    assert restored.language == language
    assert restored.settings == settings
    assert restored.scale == scale
    assert restored.input_arity == source.input_arity == 2
    assert restored.source._payload is None
    assert _evaluate(language, restored, inputs=2) == "0110"
    assert _evaluate(language, restored, inputs=2, isolated=True) == "0110"
    assert esolangs.evaluate(language, restored, [0, 1]).answer == "1"
    with pytest.raises(esolangs.ArgumentError, match="has 2 inputs"):
        esolangs.evaluate(language, restored, [0, 1, 0])


def test_plain_png_has_no_source_metadata() -> None:
    source = Raster((((1, 2, 3),),))
    restored = Raster.from_png(source.to_png())
    assert restored == source
    assert not hasattr(restored, "language")
    assert not hasattr(restored, "settings")
    assert not hasattr(restored, "scale")


def test_png_metadata_integer_fallback_preserves_json_key_rules() -> None:
    pixels = Raster((((1, 2, 3),),))
    data = pixels.to_png()
    cap = sys.int_info.str_digits_check_threshold
    large = 10**cap
    previous = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(cap)
    try:
        for value in (7, large):
            metadata = {
                "version": 1,
                "extra": {2: value, None: 0, True: 1, False: 2, 1.25: 3, "é": 4},
            }
            tagged = png.write_metadata(data, metadata)
            assert Raster.from_png(tagged) == pixels
            assert png.read_metadata(tagged) == {
                "version": 1,
                "extra": {
                    "2": value,
                    "null": 0,
                    "true": 1,
                    "false": 2,
                    "1.25": 3,
                    "é": 4,
                },
            }
            duplicate = png.write_metadata(
                data, {"version": 1, "extra": {2: value, "2": 3}}
            )
            with pytest.raises(ValueError, match="duplicate field: 2"):
                png.read_metadata(duplicate)
        tagged = png.write_metadata(data, {"version": 1, "extra": {large: "wide"}})
        assert png.read_metadata(tagged)["extra"] == {"1" + "0" * cap: "wide"}
        for key, error_type in (((1, 2), TypeError), (float("nan"), ValueError)):
            with pytest.raises(error_type):
                png.write_metadata(
                    data, {"version": 1, "integer": large, "extra": {key: 0}}
                )
    finally:
        sys.set_int_max_str_digits(previous)


def test_png_metadata_refuses_cycles_and_allows_shared_values() -> None:
    data = Raster((((1, 2, 3),),)).to_png()
    cycle = {}
    cycle["cycle"] = cycle
    sequence = []
    sequence.append((sequence,))
    shared = {"item": 3}
    cap = sys.int_info.str_digits_check_threshold
    previous = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(cap)
    try:
        for value in (7, 10**cap):
            fields = {"version": 1, "integer": value}
            for container in (cycle, sequence):
                with pytest.raises(ValueError, match=r"^Circular reference detected"):
                    png.write_metadata(data, {**fields, "value": container})
            metadata = {**fields, "value": [shared, shared]}
            assert png.read_metadata(png.write_metadata(data, metadata)) == metadata
    finally:
        sys.set_int_max_str_digits(previous)


def test_raster_scale_metadata_stays_a_json_integer(tmp_path: Path) -> None:
    api = esolangs.Language(RASTER_LANGUAGES[0])
    pixels = Raster((((1, 2, 3),),))
    original = esolangs.ProgramArtifact(pixels, api.name, scale=10**5000)
    path = tmp_path / "source.png"
    api.to_file(original, path)
    assert api.from_file(path) == original
    packed = api.to_json(original)
    assert api.from_json(packed) == original
    legacy = json.loads(packed)
    assert "scale" not in legacy
    assert base64.b64decode(legacy["source"]) == path.read_bytes()

    oversized = replace(original, scale=10**17000)
    with pytest.raises(esolangs.ProgramError, match="oversized esolangs PNG metadata"):
        api.to_file(oversized, path)
    assert api.from_file(path) == original
    packed = api.to_json(oversized)
    fallback = json.loads(packed, parse_int=str)
    assert fallback["version"] == "1"
    assert fallback["scale"] == "1" + "0" * 17000
    assert base64.b64decode(fallback["source"]) == pixels.to_png()
    assert api.from_json(packed) == oversized


def test_portable_raster_saves_settings_beyond_native_metadata_budget(
    monkeypatch,
) -> None:
    language = RASTER_LANGUAGES[0]
    original = LANGUAGES[language]
    choice = "x" * 17000
    schema = esolangs.DialectSchema(language, {"note": ("", choice)}, {"note": ""})
    runtime = replace(original.runtime, dialect=lambda **_: {}, dialect_schema=schema)
    api = esolangs.Catalog([replace(original, runtime=runtime)]).bind(language)
    generated = esolangs.generate(language, "0110", scale=2)
    artifact = replace(generated, settings=api.settings(note=choice))
    packed = api.to_json(artifact)
    restored = api.from_json(packed)
    assert restored == artifact
    assert api.to_json(restored) == packed
    module = _execution_runtime.interpreter_module(language)
    run = getattr(module, runtime.completion_entrypoint)

    def scoped_run(program, io, *, note, **options):
        assert note == choice
        return run(program, io, **options)

    monkeypatch.setattr(module, runtime.completion_entrypoint, scoped_run)
    for bits, answer in (([0, 1], "1"), ([1, 1], "0")):
        assert api.evaluate(restored, bits).answer == answer
    no_scale = replace(artifact, scale=None)
    assert api.from_json(api.to_json(no_scale)) == no_scale


def test_portable_raster_applies_settings_absent_from_png(tmp_path: Path) -> None:
    api = esolangs.Language(RASTER_LANGUAGES[0])
    pixels = Raster((((1, 2, 3),),)).upscaled(2)
    record = esolangs.ProgramArtifact(
        pixels, api.name, settings=api.settings(), scale=2
    )
    document = json.loads(api.to_json(record))
    metadata = {"version": 1, "language": api.name, "scale": 2}
    bare = pixels.to_png()
    native = png.write_metadata(bare, metadata)
    path = tmp_path / "source.png"
    path.write_bytes(native)
    assert api.from_file(path) == replace(record, settings=None)

    document["source"] = base64.b64encode(native).decode("ascii")
    assert api.from_json(json.dumps(document)) == record
    explicit_none = png.write_metadata(bare, {**metadata, "settings": None})
    for previous in (native, explicit_none):
        tagged = png.attach_source_metadata(previous, api.name, record.settings, 2)
        path.write_bytes(tagged)
        assert api.from_file(path) == record
        assert (
            png.attach_source_metadata(tagged, api.name, record.settings, None)
            is tagged
        )
    document["source"] = base64.b64encode(explicit_none).decode("ascii")
    with pytest.raises(
        esolangs.ProgramError, match="conflicting PNG and document settings"
    ):
        api.from_json(json.dumps(document))


def test_portable_scale_validates_its_type_and_embedded_agreement() -> None:
    api = esolangs.Language(RASTER_LANGUAGES[0])
    original = api.generate("01", scale=2)
    document = json.loads(api.to_json(original))
    assert api.from_json(json.dumps({**document, "scale": 2})) == original
    with pytest.raises(
        esolangs.ProgramError, match="conflicting PNG and document scale"
    ):
        api.from_json(json.dumps({**document, "scale": 3}))
    for scale in (None, False, "2", 0, -1):
        with pytest.raises(
            esolangs.ProgramError, match="scale must be a positive integer"
        ):
            api.from_json(json.dumps({**document, "scale": scale}))

    text = json.loads(esolangs.to_json(REFERENCE, "+."))
    with pytest.raises(esolangs.ProgramError, match="unexpected or missing fields"):
        esolangs.from_json(REFERENCE, json.dumps({**text, "scale": 2}))


def test_portable_png_accepts_embedded_arity_when_claims_agree(
    native_png, monkeypatch, tmp_path: Path
) -> None:
    api = esolangs.Language(RASTER_LANGUAGES[0])
    original = api.generate("01")
    document = json.loads(api.to_json(original))
    legacy = base64.b64decode(document["source"])
    assert "input_arity" not in png.read_metadata(legacy)
    assert _check_program(api.name, legacy).input_arity is None

    native = native_png(original)
    assert png.read_metadata(native)["input_arity"] == 1
    assert (
        png.attach_source_metadata(
            native, api.name, None, original.scale, input_arity=1
        )
        is native
    )
    suffix = b"unrelated bytes after IEND"
    filled = png.attach_source_metadata(
        legacy + suffix, api.name, None, None, input_arity=1
    )
    assert filled == native + suffix
    path = tmp_path / "source.png"
    path.write_bytes(filled)
    assert api.from_file(path) == original
    assert [api.evaluate(api.from_file(path), [bit]).answer for bit in (0, 1)] == [
        "0",
        "1",
    ]
    for scale, arity, field in ((2, 1, "scale"), (None, 2, "input_arity")):
        with pytest.raises(esolangs.ProgramError, match=rf"conflicting PNG {field}"):
            png.attach_source_metadata(native, api.name, None, scale, input_arity=arity)
    document["source"] = base64.b64encode(native).decode("ascii")
    assert api.from_json(json.dumps(document)) == original
    del document["input_arity"]
    assert api.from_json(json.dumps(document)) == original

    monkeypatch.setattr(png, "Image", None)
    with pytest.raises(
        esolangs.ProgramError, match="conflicting PNG and document input_arity"
    ):
        api.from_json(json.dumps({**document, "input_arity": 2}))


def test_png_owner_cannot_be_reassigned_by_a_catalog_alias(tmp_path: Path) -> None:
    owner = esolangs.Language(RASTER_LANGUAGES[0])
    declaration = owner.catalog.languages[owner.name]
    renamed = replace(declaration, name="Scoped Drawing", id="", aliases=(owner.name,))
    api = esolangs.Catalog([renamed]).bind(owner.name)
    artifact = owner.generate("01", settings=owner.settings(), scale=2)
    path = tmp_path / "source.png"
    owner.to_file(artifact, path)
    assert owner.from_file(path) == artifact
    assert owner.evaluate(owner.from_file(path), [1]).answer == "1"
    assert api.name == renamed.name
    assert api.from_source(artifact.source).language == api.name

    with pytest.raises(esolangs.ProgramError, match="stored PNG language"):
        png.attach_source_metadata(
            path.read_bytes(), api.name, None, 2, catalog=api.catalog
        )
    for load in (lambda: api.from_file(path), lambda: api.prepare(path)):
        with pytest.raises(esolangs.ProgramError, match="generated for"):
            load()
    document = json.loads(owner.to_json(artifact))
    with pytest.raises(esolangs.ProgramError, match="program language must be"):
        api.from_json(json.dumps(document))
    document["language"] = api.name
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        api.from_json(json.dumps(document))


def test_scoped_png_writers_resolve_source_aliases_without_settings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    alias = "my-drawing"
    declaration = LANGUAGES[RASTER_LANGUAGES[0]]
    scoped = replace(
        declaration, name="Scoped Drawing", id="", aliases=(alias, REFERENCE)
    )
    api = esolangs.Catalog([scoped]).bind(alias)
    text_catalog = esolangs.Catalog([replace(LANGUAGES[REFERENCE], aliases=(alias,))])
    program = api.generate("01")
    assert isinstance(program, esolangs.ProgramArtifact)
    assert isinstance(program.source, Raster)
    assert program.settings is None
    path = tmp_path / "drawing.txt.gz"
    api.to_file(program, path)
    canonical = path.read_bytes()
    raw = program.source.to_png()
    document = json.loads(api.to_json(program))

    writers = (
        lambda name, catalog: png.attach_source_metadata(
            raw,
            name,
            None,
            program.scale,
            input_arity=program.input_arity,
            catalog=catalog,
        ),
        lambda name, catalog: png.write_source(
            program.source.rows,
            name,
            None,
            program.scale,
            input_arity=program.input_arity,
            catalog=catalog,
        ),
    )
    for write in writers:
        tagged = write(alias, api.catalog)
        assert tagged == write(REFERENCE, api.catalog) == canonical
        for spelling in (alias, REFERENCE):
            with pytest.raises(esolangs.ArgumentError, match="requires text source"):
                write(spelling, text_catalog)
        path.write_bytes(tagged)
        restored = api.from_file(path)
        assert restored == program
        assert [api.evaluate(restored, [bit]).answer for bit in (0, 1)] == ["0", "1"]
        document["source"] = base64.b64encode(tagged).decode("ascii")
        assert api.from_json(json.dumps(document)) == program

        unscoped = write(REFERENCE, None)
        assert png.read_metadata(unscoped)["language"] == REFERENCE
        with pytest.raises(esolangs.ProgramError, match="requires text source"):
            png.attach_source_metadata(unscoped, None, None, 1, catalog=text_catalog)
        with pytest.raises(esolangs.ProgramError, match="stored PNG language"):
            png.attach_source_metadata(unscoped, alias, None, 1, catalog=api.catalog)

    text_settings = text_catalog.bind(REFERENCE).settings()
    with pytest.raises(esolangs.ArgumentError, match="requires text source"):
        png.attach_source_metadata(raw, None, text_settings, None, catalog=text_catalog)
    fixture = png.write_metadata(raw, {"version": 1, "language": REFERENCE})
    assert png.read_metadata(fixture)["language"] == REFERENCE
    monkeypatch.setattr(png, "Image", None)
    for write in writers:
        with pytest.raises(esolangs.ArgumentError, match="requires text source"):
            write(alias, text_catalog)
    attach, encode = writers
    assert attach(alias, api.catalog) == canonical
    with pytest.raises(esolangs.MissingDependencyError, match="image support"):
        encode(alias, api.catalog)


def test_png_retains_settings_for_a_lexical_owner(tmp_path: Path) -> None:
    declaration = esolangs.Language(RASTER_LANGUAGES[0]).catalog.languages[
        RASTER_LANGUAGES[0]
    ]
    owner = replace(declaration, name="Scoped Drawing!", id="")
    decoy = replace(
        declaration, name="Alias Drawing", id="", aliases=("scoped-drawing",)
    )
    catalog = esolangs.Catalog([owner, decoy])
    assert catalog.bind("scoped-drawing").name == decoy.name
    api = catalog.bind(owner.name)
    raster = Raster((((1, 2, 3),),))
    path = tmp_path / "source.png"
    for spelling in (" SCOPED-DRAWING ", " scoped_drawing! "):
        tagged = png.write_metadata(
            raster.to_png(), {"version": 1, "language": spelling, "settings": {}}
        )
        assert (
            png.attach_source_metadata(
                tagged, api.name, api.settings(), None, catalog=catalog
            )
            is tagged
        )
        path.write_bytes(tagged)
        assert api.from_file(path) == api.from_source(raster, settings=api.settings())
    path.write_bytes(
        png.write_metadata(
            raster.to_png(), {"version": 1, "language": "Scoped Drawing?"}
        )
    )
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        api.from_file(path)


def test_scoped_settings_hook_preserves_deliberate_failures(tmp_path: Path) -> None:
    installed = esolangs.Language(RASTER_LANGUAGES[0])
    name = installed.name
    declaration = installed.catalog.languages[name]
    schema = esolangs.DialectSchema(name, {"mode": (0, 1)}, {"mode": 0})
    failures: list[Exception] = []
    validations = []

    def validate(**choices):
        validations.append(choices)
        if failures:
            raise failures[-1]
        return choices

    runtime = replace(declaration.runtime, dialect=validate, dialect_schema=schema)
    scoped = esolangs.Catalog([replace(declaration, runtime=runtime)]).bind(name)
    settings = scoped.settings()
    artifact = replace(installed.generate("01", scale=2), settings=settings)
    raw = artifact.source.to_png()
    writers = (
        lambda: png.write_source(
            artifact.source.rows, name, settings, 2, catalog=scoped.catalog
        ),
        lambda: png.attach_source_metadata(
            raw, name, settings, 2, catalog=scoped.catalog
        ),
    )
    for write in writers:
        validations.clear()
        write()
        assert validations == [{}]
    legacy = png.write_metadata(
        raw,
        {"version": 1, "language": name, "settings": {"mode": 1}},
    )
    matching = scoped.settings(mode=1)
    validations.clear()
    assert (
        png.attach_source_metadata(legacy, name, matching, None, catalog=scoped.catalog)
        is legacy
    )
    assert validations == [{"mode": 1}]
    with pytest.raises(esolangs.ProgramError, match="conflicting PNG settings"):
        png.attach_source_metadata(
            legacy, name, scoped.settings(mode=0), None, catalog=scoped.catalog
        )

    retained = png.write_metadata(
        raw, {"version": 1, "language": name, "scale": 2, "settings": {}}
    )

    def retag():
        return png.attach_source_metadata(
            retained, name, None, 2, input_arity=1, catalog=scoped.catalog
        )

    validations.clear()
    tagged = retag()
    assert validations == [{}]
    assert tagged == png.attach_source_metadata(retained, name, None, 2, input_arity=1)
    assert validations == [{}]
    path = tmp_path / "program.png"
    path.write_bytes(tagged)
    restored = scoped.from_file(path)
    assert restored == artifact
    assert "".join(scoped.evaluate(restored, [bit]).answer for bit in (0, 1)) == "01"

    scoped.to_file(artifact, path)
    portable = scoped.to_json(artifact)
    for load in (lambda: scoped.from_file(path), lambda: scoped.from_json(portable)):
        validations.clear()
        assert load() == artifact
        assert validations == [{}]
    prepared = scoped.prepare(path)
    assert prepared.run(stdin="1").output == "1"

    nested = esolangs.Language(REFERENCE).execute(
        "+.[+]", limits=esolangs.ExecutionLimits(max_steps=2)
    )
    assert nested.observation.output == "\x01"
    timeout = esolangs.ExecutionTimeoutError("dialect hook timed out")
    timeout.bound = "preparation_timeout"
    errors = (
        esolangs.ProgramNotFoundError("policy not found"),
        esolangs.ProgramError("policy failed"),
        esolangs.ArgumentError("policy refused"),
        timeout,
    )
    for error in errors:
        error.observation = nested.observation
        error.partial_output = nested.observation.output
        failures[:] = [error]
        for load in (
            lambda: scoped.from_file(path),
            lambda: scoped.prepare(path),
            lambda: scoped.from_json(portable),
            lambda: scoped.from_source(artifact.source, settings=settings),
            *writers,
            retag,
        ):
            with pytest.raises(type(error)) as caught:
                load()
            assert caught.value is error
        for outcome in (
            scoped.execute(path),
            scoped.execute(artifact),
            scoped.execute(artifact.source, settings=settings),
        ):
            assert outcome.error is error
            assert outcome.status == ("limit" if error is timeout else "rejected")
            assert outcome.bound == (timeout.bound if error is timeout else None)
            assert outcome.observation == esolangs.ExecutionResult("", None, None, None)
        assert error.observation is nested.observation
        assert error.partial_output == "\x01"

    failures[:] = [TypeError("ordinary validation failure")]
    for load in (
        lambda: scoped.from_file(path),
        lambda: scoped.from_json(portable),
        retag,
    ):
        with pytest.raises(esolangs.ProgramError, match="invalid dialect settings"):
            load()
    assert prepared.run(stdin="0").output == "0"


def test_portable_png_checks_record_metadata_before_pillow(monkeypatch) -> None:
    api = esolangs.Language(RASTER_LANGUAGES[0])
    pixels = Raster((((1, 2, 3),),)).upscaled(2)
    record = esolangs.ProgramArtifact(
        pixels, api.name, settings=api.settings(), scale=2
    )
    document = api.to_json(record)
    assert api.from_json(document) == record
    value = json.loads(document)
    monkeypatch.setattr(png, "Image", None)
    for changes, message in (
        ({"input_arity": False}, "input_arity must be a positive integer"),
        ({"scale": 0}, "scale must be a positive integer"),
        ({"scale": 3}, "conflicting PNG and document scale"),
        ({"settings": None}, "conflicting PNG and document settings"),
    ):
        with pytest.raises(esolangs.ProgramError, match=message):
            api.from_json(json.dumps(value | changes))
    with pytest.raises(esolangs.MissingDependencyError):
        api.from_json(document)


def test_scaling_composes_retained_factors(native_png) -> None:
    source = esolangs.generate(RASTER_LANGUAGES[0], "01", scale=2)
    decoded = _check_program(source.language, native_png(source))
    enlarged = esolangs.ProgramArtifact(
        decoded.source.upscaled(3),
        decoded.language,
        settings=decoded.settings,
        scale=decoded.scale * 3,
    )
    assert _check_program(source.language, native_png(enlarged)).scale == 6


def test_png_settings_retain_integer_choices(tmp_path: Path) -> None:
    """Integers travel as hex; a settings tag needs its language (1.0 audit)."""
    key = integer_setting()
    owner, choices = next(
        (n, lang.runtime.dialect_schema.choices[key])
        for n, lang in LANGUAGES.items()
        if key
        in (lang.runtime.dialect_schema.choices if lang.runtime.dialect_schema else {})
    )
    raster = LANGUAGES[RASTER_LANGUAGES[0]]
    dialect = LANGUAGES[owner].runtime
    schema = dialect.dialect_schema
    assert schema is not None
    runtime = replace(
        raster.runtime,
        dialect=dialect.dialect,
        dialect_schema=esolangs.DialectSchema(
            raster.name, schema.choices, schema.defaults
        ),
    )
    api = CATALOG.with_language(replace(raster, runtime=runtime)).bind(raster.name)
    settings = api.settings(**{key: choices[-1]})
    pixels = Raster((((1, 2, 3),),))
    path = tmp_path / "settings.png"
    api.to_file(api.from_source(pixels, settings=settings), path)
    assert api.from_file(path).settings == settings
    huge = 1 << 20_000  # Past CPython's decimal rendering cap.
    with pytest.raises(esolangs.ArgumentError, match="integer with 20001 bits"):
        api.settings(**{key: huge})
    forged = api.settings()
    object.__setattr__(forged, "_items", ((key, huge),))
    with pytest.raises(
        esolangs.ArgumentError, match="invalid value for dialect setting"
    ):
        esolangs.ProgramArtifact(pixels, api.name, settings=forged)


def test_png_language_tag_refuses_cross_language_execution(native_png) -> None:
    source = esolangs.generate(RASTER_LANGUAGES[0], "01")
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        esolangs.run(
            RASTER_LANGUAGES[1],
            native_png(source),
            limits=esolangs.ExecutionLimits(max_steps=1000),
        )


def test_tagging_unknown_pixels_preserves_automatic_scale_detection() -> None:
    rows = (((255, 0, 0),) * 4,) * 4
    source = esolangs.ProgramArtifact(Raster(rows), RASTER_LANGUAGES[0])
    assert source.scale is None
    assert source.source._normalized() == (((255, 0, 0),),)


@pytest.mark.parametrize("scale", [0, True, -1])
def test_retained_scale_is_validated(scale) -> None:
    with pytest.raises(esolangs.ArgumentError, match="scale"):
        esolangs.ProgramArtifact(
            Raster((((1, 2, 3),),)), RASTER_LANGUAGES[0], scale=scale
        )


@pytest.mark.medium
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_explicit_scale_overrides_png_metadata(
    language, monkeypatch, native_png, tmp_path: Path
) -> None:
    module = _execution_runtime.interpreter_module(language)
    assert not hasattr(module, "supports_scale")
    monkeypatch.setattr(module, "supports_scale", False, raising=False)
    source = esolangs.generate(language, "01", scale=2)
    changed = esolangs.ProgramArtifact(Raster(source.source.rows), language, scale=7)
    result = esolangs.run(
        language,
        native_png(changed),
        stdin=esolangs.encode_inputs(language, [1]),
        scale=2,
        limits=esolangs.ExecutionLimits(max_steps=1000),
    )
    assert esolangs.read_answer(language, result.output) == "1"
    spec = LANGUAGES[language]
    caps = replace(spec.runtime.capabilities, supports_scale=False)
    runtime = replace(spec.runtime, capabilities=caps)
    catalog = CATALOG.with_language(replace(spec, runtime=runtime))
    monkeypatch.setattr(module, "supports_scale", True)
    with pytest.raises(esolangs.ArgumentError, match="scale"):
        esolangs.run(language, changed, scale=2, catalog=catalog)

    scoped = catalog.bind(language)
    for balance in (False, True):
        generated = scoped.generate("01", balance=balance)
        assert generated.scale is None
        assert scoped.generate("01", balance=balance, scale=1) == generated
        path = tmp_path / "native.png"
        scoped.to_file(generated, path)
        native = scoped.from_file(path)
        portable = scoped.from_json(scoped.to_json(generated))
        assert generated == native == portable
        for record in (generated, native, portable):
            assert "".join(scoped.evaluate(record, [b]).answer for b in (0, 1)) == "01"
    with pytest.raises(esolangs.ArgumentError, match="does not support raster scaling"):
        scoped.generate("01", scale=2)
