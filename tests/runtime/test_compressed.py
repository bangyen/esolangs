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


def test_compressed_writers_publish_only_after_success(
    tmp_path: Path, monkeypatch
) -> None:
    program = CompressedText.repeated("+", 1)
    destination = tmp_path / "source.gz"
    destination.write_bytes(b"existing file")

    def refuse_replace(staged, requested):
        assert requested == destination
        assert staged.read_bytes() == program.to_gzip()
        raise PermissionError("replacement refused")

    monkeypatch.setattr(Path, "replace", refuse_replace)
    for save in (
        program.to_file,
        lambda path: esolangs.to_file(REFERENCE, program, path, gzip=True),
    ):
        with pytest.raises(
            esolangs.ProgramError, match=r"source\.gz.*replacement refused"
        ):
            save(destination)
        assert destination.read_bytes() == b"existing file"
        assert list(tmp_path.iterdir()) == [destination]


def test_compressed_writers_replace_links_without_changing_the_referent(
    tmp_path: Path,
) -> None:
    program = CompressedText.repeated("+", 1)
    original = tmp_path / "original.gz"
    original.write_bytes(b"original")
    destination = tmp_path / "link.gz"
    for save in (
        program.to_file,
        lambda path: esolangs.to_file(REFERENCE, program, path, gzip=True),
    ):
        try:
            destination.symlink_to(original)
        except OSError as error:
            pytest.skip(f"symlinks unavailable: {error}")
        save(destination)
        assert not destination.is_symlink()
        assert destination.read_bytes() == program.to_gzip()
        assert original.read_bytes() == b"original"
        destination.unlink()


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


def test_oversized_repeat_reports_the_work_cap_without_rendering() -> None:
    cap = 10**5000
    limits = esolangs.TextLimits(plain_chars=0, generation_chars=cap, gzip_bytes=100)
    with pytest.raises(esolangs.GeneratorCapError, match="character work cap"):
        CompressedText.repeated("x", cap + 1, limits=limits)


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


def test_compression_revalidates_budget_fields_from_a_subclass() -> None:
    class UncheckedLimits(esolangs.TextLimits):
        def __post_init__(self) -> None:
            pass

    limits = UncheckedLimits(plain_chars=-1, generation_chars=2, gzip_bytes=100)
    with pytest.raises(esolangs.ArgumentError, match="nonnegative"):
        CompressedText.from_chunks(("..",), limits=limits)


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


def test_wrapping_counts_the_newline_at_an_exact_width() -> None:
    class Width(int):
        def __int__(self) -> int:
            return 1

    limits = esolangs.TextLimits(plain_chars=3, generation_chars=3, gzip_bytes=100)
    program = CompressedText.from_chunks(("ab",), limits=limits)
    assert program.wrapped(Width(2)) == program.wrapped(2)
    assert str(program.wrapped(2)) == "ab\n"
    with pytest.raises(esolangs.GeneratorCapError, match="work cap"):
        program.wrapped(1)


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
