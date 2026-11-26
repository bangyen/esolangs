"""Compressed transport preserves source, provenance and expanded size."""

import gzip
import os
import pickle
import stat
from os import fspath
from pathlib import Path

import pytest

import esolangs
from esolangs import serialization
from esolangs.compressed import CompressedText
from esolangs.runtime import _files, _publish
from esolangs.runtime._files import explicit_path
from esolangs.runtime._publish import write_staged
from esolangs.runtime._source import text_source
from scripts.source_units import source_units
from tests.support.reference import REFERENCE


def test_pickles_require_measured_line_metadata() -> None:
    program = CompressedText.from_chunks(("a\nb",))
    restored = pickle.loads(pickle.dumps(program))
    assert restored.to_gzip() == program.to_gzip()
    assert restored._is_multiline()
    assert restored._last_character() == "b"
    for field in ("_has_newline", "_tail"):
        incomplete = pickle.loads(pickle.dumps(program))
        object.__delattr__(incomplete, field)
        with pytest.raises(ValueError, match="requires measured line metadata"):
            pickle.loads(pickle.dumps(incomplete))


def test_streaming_text_round_trip_and_size(tmp_path: Path, monkeypatch) -> None:
    source = "aÿ\n" * 30000
    program = CompressedText.from_chunks((source[:65535], source[65535:]))
    assert str(program) == source
    assert len(program) == len(source)
    assert program.to_gzip()[8] == 2  # Gzip XFL marks maximum compression.
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

    archive = gzip.compress(b"", mtime=0) * 1024 + gzip.compress(b"+.", mtime=0)
    api = esolangs.Language(REFERENCE)
    with _files.stream_read_deadline(float("inf")):
        restored = api.from_json(api.to_json(archive))
        assert restored.source.to_gzip() == archive
    assert api.prepare(restored).run().unwrap().output == "\x01"

    finish_member = gzip._GzipReader._read_eof
    members = 0

    def observed_finish(reader):
        nonlocal members
        finish_member(reader)
        members += 1

    monkeypatch.setattr(gzip._GzipReader, "_read_eof", observed_finish)
    monkeypatch.setattr(_files, "monotonic", lambda: 1.0 if members else 0.0)
    with _files.stream_read_deadline(1.0), pytest.raises(_files.StreamReadTimeoutError):
        CompressedText(archive)
    assert 0 < members < 1025


def test_compressed_writers_publish_only_after_success(
    tmp_path: Path, monkeypatch
) -> None:
    program = CompressedText.repeated("+", 1)
    destination = tmp_path / "source.gz"
    destination.write_bytes(b"existing file")

    def refuse_replace(staged, requested, *, src_dir_fd=None, dst_dir_fd=None):
        if dst_dir_fd is None:
            assert fspath(requested) == fspath(destination)
        else:
            assert requested == destination.name
            assert os.path.samestat(os.fstat(dst_dir_fd), tmp_path.stat())
        with open(
            staged,
            "rb",
            opener=lambda name, flags: os.open(name, flags, dir_fd=src_dir_fd),
        ) as file:
            assert file.read() == program.to_gzip()
        raise PermissionError("replacement refused")

    for anchored in dict.fromkeys((_publish._ANCHORED_STAGING, False)):
        monkeypatch.setattr(_publish, "_ANCHORED_STAGING", anchored)
        destination.write_bytes(b"existing file")
        with monkeypatch.context() as patch:
            patch.setattr(os, "replace", refuse_replace)
            for save in (
                program.to_file,
                lambda path: serialization.to_file(REFERENCE, program, path, gzip=True),
            ):
                with pytest.raises(
                    esolangs.ProgramError, match=r"source\.gz.*replacement refused"
                ):
                    save(destination)
                assert destination.read_bytes() == b"existing file"
                assert list(tmp_path.iterdir()) == [destination]
        program.to_file(destination)
        assert destination.read_bytes() == program.to_gzip()
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
        lambda path: serialization.to_file(REFERENCE, program, path, gzip=True),
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


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX permission bits")
def test_native_writers_preserve_regular_destination_permissions(
    tmp_path: Path,
) -> None:
    program = CompressedText.repeated("+", 1)
    original = tmp_path / "private-source"
    original.write_bytes(b"original")
    original.chmod(0o600)
    destination = tmp_path / "export"
    previous_mask = os.umask(0o022)
    try:
        for save in (
            program.to_file,
            lambda path: serialization.to_file(REFERENCE, program, path, gzip=True),
        ):
            destination.hardlink_to(original)
            save(destination)
            assert destination.read_bytes() == program.to_gzip()
            assert stat.S_IMODE(destination.stat().st_mode) == 0o600
            assert original.read_bytes() == b"original"
            assert stat.S_IMODE(original.stat().st_mode) == 0o600

            destination.unlink()
            save(destination)
            assert stat.S_IMODE(destination.stat().st_mode) == 0o644

            destination.unlink()
            destination.symlink_to(original)
            save(destination)
            assert not destination.is_symlink()
            assert stat.S_IMODE(destination.stat().st_mode) == 0o644
            assert stat.S_IMODE(original.stat().st_mode) == 0o600
            destination.unlink()
    finally:
        os.umask(previous_mask)


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX permission bits")
def test_staged_write_uses_mode_tightened_during_writing(tmp_path: Path) -> None:
    destination = tmp_path / "export"
    destination.write_bytes(b"old source")
    destination.chmod(0o644)

    def chunks():
        yield b"new "
        assert destination.read_bytes() == b"old source"
        destination.chmod(0o600)
        yield b"source"

    write_staged(explicit_path(destination), chunks())
    assert destination.read_bytes() == b"new source"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600


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
    with pytest.raises(esolangs.ProgramError) as unbounded:
        CompressedText(data)
    with (
        _files.stream_read_deadline(float("inf")),
        pytest.raises(esolangs.ProgramError) as bounded,
    ):
        CompressedText(data)
    assert str(bounded.value) == str(unbounded.value)
    assert bounded.value.__notes__ == unbounded.value.__notes__


@pytest.mark.parametrize("tail", [b"\xf0\x9f\xff", b"\xf0\x9f"])
def test_invalid_utf8_offset_spans_gzip_decode_blocks(tail: bytes, monkeypatch) -> None:
    monkeypatch.setattr("esolangs.compressed._BLOCK", 4)
    invalid = gzip.compress(b"abc" + tail, mtime=0)
    with pytest.raises(esolangs.ProgramError, match="invalid UTF-8 at decoded byte 3"):
        CompressedText(invalid)


def test_existing_gzip_counts_only_through_first_chunk_over_budget(monkeypatch) -> None:
    data = gzip.compress(b"abcd", mtime=0)
    read = gzip.GzipFile.read
    sizes = []

    def observed_read(stream, size=-1):
        sizes.append(size)
        return read(stream, size)

    monkeypatch.setattr("esolangs.compressed._BLOCK", 2)
    monkeypatch.setattr(gzip.GzipFile, "read", observed_read)
    limits = esolangs.TextLimits(plain_chars=0, generation_chars=1, gzip_bytes=100)
    with pytest.raises(esolangs.GeneratorCapError, match="work cap"):
        CompressedText(data, limits=limits)
    assert sizes == [2]


def test_gzip_cap_below_empty_member_refuses_before_acquiring_chunks() -> None:
    class Unreadable:
        def __iter__(self):
            pytest.fail("an impossible gzip cap acquired the chunk provider")

    limits = esolangs.TextLimits(plain_chars=0, generation_chars=0, gzip_bytes=19)
    with pytest.raises(esolangs.ArgumentError, match="chunks must be an iterable"):
        CompressedText.from_chunks(None, limits=limits)
    with pytest.raises(esolangs.GeneratorCapError, match="19-byte file cap"):
        CompressedText.from_chunks(Unreadable(), limits=limits)


def test_empty_gzip_member_fits_exact_byte_cap() -> None:
    class Chunks:
        def __getitem__(self, index):
            if index == 0:
                return "+."
            raise IndexError

    assert CompressedText.from_chunks(Chunks()) == CompressedText.from_chunks(("+.",))

    class Disabled(Chunks):
        __iter__ = None

    with pytest.raises(esolangs.ArgumentError, match="chunks must be an iterable"):
        CompressedText.from_chunks(Disabled())

    class DescriptorChunks:
        @classmethod
        def __getitem__(cls, index):
            if index == 0:
                return "+."
            raise IndexError

    assert CompressedText.from_chunks(DescriptorChunks()) == CompressedText.from_chunks(
        ("+.",)
    )

    class BrokenChunks:
        def __getitem__(self, _index):
            raise RuntimeError("could not acquire chunk")

    with pytest.raises(RuntimeError, match="could not acquire chunk"):
        CompressedText.from_chunks(BrokenChunks())

    class InvalidChunks:
        def __getitem__(self, _index):
            return 42

    with pytest.raises(esolangs.ArgumentError, match="chunks must be strings"):
        CompressedText.from_chunks(InvalidChunks())
    limits = esolangs.TextLimits(plain_chars=0, generation_chars=0, gzip_bytes=20)
    empty = CompressedText.from_chunks((), limits=limits)
    assert len(empty.to_gzip()) == 20
    assert CompressedText(empty.to_gzip(), limits=limits) == empty
    api = esolangs.Language(REFERENCE)
    assert api.from_json(api.to_json(empty)).source == empty


def test_oversized_repeat_reports_the_work_cap_without_rendering() -> None:
    class Count(int):
        def __int__(self):
            raise AssertionError("converted subclass")

        def __lt__(self, other):
            raise AssertionError("compared subclass")

    assert CompressedText.repeated("+", Count(2)) == CompressedText.repeated("+", 2)
    for bad in (Count(-1), True, 2.0):
        with pytest.raises(esolangs.ArgumentError, match="nonnegative count"):
            CompressedText.repeated("+", bad)
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
    assert api.prepare(artifact).run().unwrap().output == "\x01"
    for limits in (
        None,
        esolangs.ExecutionLimits(max_steps=2),
        esolangs.ExecutionLimits(total_timeout=5),
    ):
        assert api.run(artifact, limits=limits).unwrap().output == "\x01"
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


def test_compressed_source_retains_language_origin(tmp_path: Path) -> None:
    program = esolangs.ProgramArtifact(CompressedText.from_chunks((",.",)), REFERENCE)
    assert esolangs.run(REFERENCE, program, stdin="Z").unwrap().output == "Z"
    other = next(n for n in esolangs.list_languages() if n != REFERENCE)
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        esolangs.run(
            REFERENCE, esolangs.ProgramArtifact(program.source, other), stdin="Z"
        ).unwrap()

    class AlternateChunks(CompressedText):
        def chunks(self):
            yield "+++."

    api = esolangs.Language(REFERENCE)
    archive = program.source.to_gzip()
    limits = esolangs.TextLimits(plain_chars=3, generation_chars=3, gzip_bytes=100)
    supplied = AlternateChunks(archive, limits=limits)
    assert len(supplied) == 2
    assert str(supplied) == ",."
    assert str(supplied.wrapped(2)) == ",.\n"
    assert api.run(supplied, stdin="Z").unwrap().output == "Z"

    artifact = api.from_source(supplied)
    assert type(artifact.source) is CompressedText
    assert artifact.source.limits is limits
    portable = api.from_json(api.to_json(artifact))
    assert portable == artifact
    destination = tmp_path / "retained.gz"
    api.to_file(supplied, destination, gzip=True)
    assert destination.read_bytes() == archive
    for restored in (artifact, portable, api.from_file(destination)):
        assert api.run(restored, stdin="Z").unwrap().output == "Z"

    with pytest.raises(esolangs.ProgramError, match="invalid gzip source"):
        AlternateChunks(b"not gzip")


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

    class Budget(int):
        def __int__(self):
            raise AssertionError("converted the budget subclass")

        def __lt__(self, other):
            raise AssertionError("compared the budget subclass")

    budgets = TextLimits(
        plain_chars=Budget(1), generation_chars=Budget(2), gzip_bytes=Budget(100)
    )
    assert all(
        type(value) is int
        for value in (budgets.plain_chars, budgets.generation_chars, budgets.gzip_bytes)
    )
    compressed = CompressedText.from_chunks(("x",), limits=budgets)
    api = esolangs.Language(REFERENCE)
    artifact = api.from_source(compressed)
    assert api.from_json(api.to_json(artifact)) == artifact
    for bad in (-1, Budget(-1), True, 1.0):
        with pytest.raises(esolangs.ArgumentError, match="nonnegative"):
            TextLimits(plain_chars=1, generation_chars=bad, gzip_bytes=1)
