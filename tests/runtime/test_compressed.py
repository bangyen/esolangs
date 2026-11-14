"""Compressed transport preserves source, provenance and expanded size."""

import gzip
from pathlib import Path

import pytest

import esolangs
from esolangs.compressed import CompressedText
from esolangs.runtime._source import text_source
from scripts.source_units import source_units
from tests.support.reference import REFERENCE


def test_streaming_text_round_trip_and_size(tmp_path: Path) -> None:
    source = "aÿ\n" * 30000
    program = CompressedText.from_chunks((source[:65535], source[65535:]))
    assert str(program) == source
    assert len(program) == len(source)
    assert source_units(program) == len(source)
    assert text_source(program.to_gzip()) == source
    path = tmp_path / "source.gz"
    program.to_file(path)
    assert text_source(path) == source
    assert program.to_gzip() == CompressedText.from_chunks((source,)).to_gzip()
    empty = CompressedText.from_chunks(("",))
    assert len(empty) == 0
    assert str(empty) == ""
    assert empty.data
    with pytest.raises(esolangs.ProgramError, match="no gzip member"):
        CompressedText(b"")


@pytest.mark.parametrize(
    "data",
    [
        b"plain",
        b"\x1f\x8b",
        gzip.compress(b"\xff", mtime=0),
        gzip.compress(b"abc", mtime=0)[:-1],
    ],
    ids=["plain", "truncated_header", "invalid_utf8", "truncated_payload"],
)
def test_corrupt_or_non_utf8_gzip_is_a_program_error(data: bytes) -> None:
    with pytest.raises(esolangs.ProgramError):
        CompressedText(data)


def test_existing_gzip_counts_only_through_first_chunk_over_budget() -> None:
    class Monitored(CompressedText):
        def chunks(self):
            yield "ab"
            pytest.fail("source kept decoding after exceeding its generation-work cap")

    data = gzip.compress(b"abcd", mtime=0)
    limits = esolangs.TextLimits(plain_chars=0, generation_chars=1, gzip_bytes=100)
    with pytest.raises(esolangs.GeneratorCapError, match="work cap"):
        Monitored(data, limits=limits)


def test_gzip_budget_and_hash_use_builtin_bytes() -> None:
    class Buffer(bytes):
        __hash__ = None

        def __len__(self):
            return 1

        def __bytes__(self):
            return b"unrelated"

    data = gzip.compress(b"x", mtime=0)
    buffer = Buffer(data)
    original = CompressedText(data)
    restored = CompressedText(buffer)
    assert type(restored.data) is bytes
    assert hash(restored) == hash(original)
    assert restored.to_gzip() == data
    limits = esolangs.TextLimits(plain_chars=1, generation_chars=1, gzip_bytes=1)
    with pytest.raises(esolangs.GeneratorCapError, match="file cap"):
        CompressedText(buffer, limits=limits)


def test_compression_uses_underlying_string_contents_and_length() -> None:
    class Text(str):
        def __len__(self):
            return 100

        def __str__(self):
            return "other"

        def encode(self, *_args, **_kwargs):
            return b"other"

    limits = esolangs.TextLimits(plain_chars=2, generation_chars=2, gzip_bytes=100)
    compressed = CompressedText.from_chunks((Text("x"), Text("x")), limits=limits)
    assert compressed == CompressedText(compressed.to_gzip(), limits=limits)
    assert compressed == CompressedText.repeated(Text("x"), 2, limits=limits)
    assert str(compressed) == "xx"


@pytest.mark.medium
def test_raw_export_cap_does_not_prevent_loading_compressed_source(
    tmp_path: Path,
) -> None:
    api = esolangs.Language(REFERENCE)
    budget = esolangs.TextLimits(plain_chars=0, generation_chars=2, gzip_bytes=100)
    compressed = CompressedText.from_chunks(("+.",), limits=budget)
    artifact = api.from_source(compressed)
    assert api.prepare(artifact).run().output == "\x01"
    for limits in (
        None,
        esolangs.ExecutionLimits(max_steps=2),
        esolangs.ExecutionLimits(total_timeout=5),
    ):
        assert api.run(artifact, limits=limits).output == "\x01"
    path = tmp_path / "program"
    with pytest.raises(esolangs.GeneratorCapError, match="raw text"):
        api.to_file(artifact, path)
    api.to_file(artifact, path, gzip=True)
    assert path.read_bytes() == compressed.to_gzip()
    with pytest.raises(esolangs.GeneratorCapError, match="work cap"):
        CompressedText.from_chunks(("++.",), limits=budget)


def test_wrapping_preserves_characters_and_bounds_lines() -> None:
    program = CompressedText.repeated("x", 100000)
    wrapped = program.wrapped(37)
    assert str(wrapped).replace("\n", "") == str(program)
    assert max(map(len, str(wrapped).splitlines())) == 37
    assert program.wrapped(None) is program
    with pytest.raises(ValueError, match="width"):
        program.wrapped(0)
    with pytest.raises(ValueError, match="character"):
        CompressedText.repeated("xx", 1)


def test_compressed_source_retains_language_origin() -> None:
    program = esolangs.ProgramArtifact(CompressedText.from_chunks((",.",)), REFERENCE)
    assert esolangs.run(REFERENCE, program, stdin="Z").output == "Z"
    other = next(n for n in esolangs.list_languages() if n != REFERENCE)
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        esolangs.run(
            REFERENCE, esolangs.ProgramArtifact(program.source, other), stdin="Z"
        )


def test_format_budgets_are_independent_and_survive_wrapping() -> None:
    from esolangs.compressed import TextLimits

    limits = TextLimits(plain_chars=5, generation_chars=30, gzip_bytes=100)
    program = CompressedText.repeated("x", 10, limits=limits)
    assert len(program) == 10
    assert "".join(program.chunks()) == "x" * 10
    assert len(program.to_gzip()) < limits.gzip_bytes
    for export in (lambda: str(program), program.plain_chunks):
        with pytest.raises(esolangs.GeneratorCapError, match="raw text"):
            export()
    wrapped = program.wrapped(3)
    assert wrapped.limits == limits
    assert esolangs.ProgramArtifact(wrapped, REFERENCE).source.limits == limits
    with pytest.raises(esolangs.GeneratorCapError, match="work cap"):
        CompressedText.repeated("x", 31, limits=limits)
    with pytest.raises(esolangs.GeneratorCapError, match="work cap"):
        program.wrapped(1).wrapped(1)
    with pytest.raises(esolangs.GeneratorCapError, match="file cap"):
        CompressedText.from_chunks(
            ("x",), limits=TextLimits(plain_chars=10, generation_chars=10, gzip_bytes=1)
        )
    with pytest.raises(esolangs.ArgumentError, match="nonnegative"):
        TextLimits(plain_chars=1, generation_chars=-1, gzip_bytes=1)
