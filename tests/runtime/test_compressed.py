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
