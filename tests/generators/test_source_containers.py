"""Execution keeps the same behavior across source and input containers."""

import gzip
import io
from pathlib import Path
from threading import Event
from typing import Any

import pytest

import esolangs
from esolangs.debugger import make_debugger
from esolangs.operations.source import _check_program
from esolangs.registry import LANGUAGES
from tests.support.evaluation import _evaluate
from tests.support.pick import languages, one_where
from tests.support.reference import REFERENCE

_RASTERS = languages(source_kind="raster", boolean_generator=True)


def _native_bytes(program, tmp_path: Path) -> bytes:
    if isinstance(program.source, esolangs.Raster):
        path = tmp_path / "source.png"
        esolangs.to_file(program.language, program, path)
        restored = esolangs.Language(program.language).from_file(path)
        assert (restored.language, restored.settings, restored.scale) == (
            program.language,
            program.settings,
            program.scale,
        )
        for other in _RASTERS:
            if other != program.language:
                with pytest.raises(esolangs.ProgramError, match="generated for"):
                    esolangs.Language(other).from_file(path)
        return path.read_bytes()
    return program.source.encode()


# Isolation forwards whatever the container held, so one container covers it;
# each isolated case spawns a worker. Raster text streams are binary streams;
# exercise that container once.
@pytest.mark.parametrize(
    ("language", "holder", "mode"),
    [
        pytest.param(
            language,
            holder,
            mode,
            marks=(pytest.mark.medium,) if mode == "isolated" else (),
        )
        for language in [REFERENCE, *_RASTERS]
        for holder, mode in (
            ("bytes", "normal"),
            ("text_stream", "normal"),
            ("binary_stream", "normal"),
            ("bytes", "isolated"),
        )
        if holder != "text_stream" or language == REFERENCE
    ],
)
def test_execution_container_parity(
    language: str, holder: str, mode: str, tmp_path: Path
) -> None:
    program = esolangs.generate(language, "01")
    data = _native_bytes(program, tmp_path)
    source: Any = data
    if holder == "text_stream":
        source = io.StringIO(program.source)
    elif holder == "binary_stream":
        source = io.BytesIO(data)
    stdin = io.BytesIO(b"1")
    bounds: dict[str, Any] = {}
    if mode == "isolated":
        bounds["isolated"] = True
    assert esolangs.run(language, source, stdin=stdin, **bounds).output == "1"
    assert stdin.tell() == 1
    assert not stdin.closed
    if hasattr(source, "closed"):
        assert not source.closed


@pytest.mark.parametrize("language", [REFERENCE, *_RASTERS])
def test_streams_work_with_bound_api_debugging_and_evaluation(
    language: str, tmp_path: Path
) -> None:
    api = esolangs.Language(language)
    program = api.generate("01")
    data = _native_bytes(program, tmp_path)
    assert _evaluate(api.name, io.BytesIO(data), inputs=1) == "01"
    debugger = make_debugger(language, io.BytesIO(data), stdin=io.StringIO("1"))
    assert debugger.run(limits=esolangs.ExecutionLimits(max_steps=10000)) == "halted"
    assert debugger.output == "1"


def test_nonseekable_streams_are_read_once_from_the_current_position() -> None:
    class Stream:
        def __init__(self, value: str | bytes) -> None:
            self.value = value
            self.reads = 0

        def read(self) -> str | bytes:
            self.reads += 1
            assert self.reads == 1
            return self.value

    program, stdin = Stream(b",.,."), Stream("\n\x00")
    assert _check_program(REFERENCE, program, stdin).source == ",.,."
    assert stdin.reads == 0
    assert esolangs.run(REFERENCE, ",.,.", stdin=stdin).output == "\n\x00"
    assert (program.reads, stdin.reads) == (1, 1)
    source = io.StringIO("ignored,.")
    source.seek(7)
    assert esolangs.run(REFERENCE, source, stdin="Z").output == "Z"


@pytest.mark.parametrize(
    "stdin", ["é", "é".encode(), io.StringIO("é"), io.BytesIO("é".encode())]
)
def test_binary_stdin_uses_the_same_unicode_character_stream(stdin: Any) -> None:
    assert esolangs.run(REFERENCE, ",.", stdin=stdin).output == "é"


def test_path_loading_is_lossless_with_explicit_native_normalization(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.txt"
    path.write_bytes(b"+,\r\n.\r\n")
    api = esolangs.Language(REFERENCE)
    assert api.from_file(path).source == "+,\r\n.\r\n"
    assert api.from_file(path, normalize=True).source == "+,\n."
    api.to_file(api.from_file(path), path)
    assert path.read_bytes() == b"+,\r\n.\r\n"
    assert _check_program(REFERENCE, path).source == "+,\r\n.\r\n"
    assert esolangs.run(REFERENCE, path, stdin="Q").output == "Q"


@pytest.mark.parametrize("gzip_output", [False, True])
def test_native_terminator_does_not_absorb_a_lone_cr(
    tmp_path: Path, *, gzip_output: bool
) -> None:
    api = esolangs.Language(REFERENCE)
    text = "+.\r"
    path = tmp_path / "source"
    for source in (text, esolangs.CompressedText.from_chunks((text,))):
        api.to_file(source, path, gzip=gzip_output, normalize=True)
        assert api.from_file(path, normalize=True).source == "+.\n"
        api.to_file(source, path, gzip=gzip_output)
        wire = path.read_bytes()
        assert (gzip.decompress(wire) if gzip_output else wire) == text.encode()


def test_two_byte_native_terminator_counts_toward_raw_budget(tmp_path: Path) -> None:
    limits = esolangs.TextLimits(plain_chars=4, generation_chars=5, gzip_bytes=100)
    compressed = esolangs.CompressedText.from_chunks(("+.\r",), limits=limits)
    path = tmp_path / "source"
    path.write_bytes(b"original")
    with pytest.raises(esolangs.GeneratorCapError, match="raw text"):
        esolangs.to_file(REFERENCE, compressed, path, normalize=True)
    assert path.read_bytes() == b"original"


@pytest.mark.parametrize("spelling", ["", b"bytes", 1])
def test_explicit_paths_are_validated_on_import_and_export(spelling) -> None:
    class BadPath:
        def __fspath__(self):
            return spelling

    for path in ("", BadPath()):
        with pytest.raises(esolangs.ArgumentError, match="path"):
            esolangs.from_file(REFERENCE, path)
        with pytest.raises(esolangs.ArgumentError, match="path"):
            esolangs.to_file(REFERENCE, "+.", path)


def test_file_diagnostics_use_the_validated_path_once(tmp_path: Path) -> None:
    class ProgramPath:
        def __init__(self, path: Path) -> None:
            self.path = path
            self.reads = 0

        def __fspath__(self) -> str:
            self.reads += 1
            assert self.reads == 1
            return str(self.path)

        def __str__(self) -> str:
            raise RuntimeError("the path protocol supplies the filename")

    source = tmp_path / "invalid.bf"
    source.write_bytes(b"\xff")
    api = esolangs.Language(REFERENCE)
    for read in (api.run, api.prepare, api.to_json, api.from_file):
        wrapped = ProgramPath(source)
        with pytest.raises(esolangs.ProgramError, match="invalid UTF-8") as caught:
            read(wrapped)
        assert str(source) in str(caught.value)
        assert wrapped.reads == 1

    missing = ProgramPath(tmp_path / "missing.bf")
    with pytest.raises(esolangs.ProgramNotFoundError, match=r"missing\.bf"):
        api.run(missing)
    blocked = ProgramPath(tmp_path / "missing" / "destination.bf")
    with pytest.raises(esolangs.ProgramError, match=r"destination\.bf"):
        api.to_file("+.", blocked)


@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize(
    "language", one_where(lambda info: LANGUAGES[info.name].runtime.compressed_source)
)
def test_compressed_language_honors_native_newlines(
    tmp_path: Path, language: str, *, compressed: bool
) -> None:
    api = esolangs.Language(language)
    # Put the first CRLF across gzip read chunks.
    body = "0" * 65535 + "\r\n0\r0\n"
    path = tmp_path / "source"
    api.to_file(body, path, gzip=compressed, normalize=True)
    assert str(api.from_file(path).source) == body + "\n"
    native = api.from_file(path, normalize=True).source
    assert isinstance(native, esolangs.CompressedText if compressed else str)
    assert str(native) == body.replace("\r\n", "\n").replace("\r", "\n")


def test_source_declaration_and_export_validate_the_language_kind(
    tmp_path: Path,
) -> None:
    for name, source in (
        (_RASTERS[0], "+."),
        (REFERENCE, esolangs.Raster((((0, 0, 0),),))),
    ):
        path = tmp_path / "source"
        with pytest.raises(esolangs.ProgramError):
            esolangs.from_source(name, source)
        for supplied in (source, esolangs.ProgramArtifact(source, name)):
            with pytest.raises(esolangs.ProgramError):
                esolangs.to_file(name, supplied, path)
            assert not path.exists()


def test_raw_and_stream_sources_use_the_underlying_string_or_bytes() -> None:
    class Text(str):
        def __str__(self):
            raise AssertionError("use the stored source text")

    class Blob(bytes):
        def startswith(self, *_args):
            raise AssertionError("detect the underlying byte signature")

        def decode(self, *_args):
            raise AssertionError("decode the underlying bytes")

    class Stream:
        def __init__(self, source):
            self.source = source
            self.reads = 0

        def read(self):
            self.reads += 1
            assert self.reads == 1
            return self.source

    api = esolangs.Language(REFERENCE)
    expected = api.from_source("+.")
    for source in (Text("+."), Blob(b"+.")):
        assert api.run(source).output == "\x01"
        stream = Stream(source)
        assert api.run(stream).output == "\x01"
        assert stream.reads == 1
        assert api.from_json(api.to_json(Stream(source))) == expected


@pytest.mark.medium
def test_stdin_subclasses_keep_the_same_bytes_in_every_execution_route() -> None:
    class Text(str):
        def __getitem__(self, _key):
            return "X"

    class Blob(bytes):
        def decode(self, *_args):
            return "X"

    for stdin in (Text("A"), Blob(b"A")):
        for limits in (
            None,
            esolangs.ExecutionLimits(max_steps=10),
            esolangs.ExecutionLimits(total_timeout=5),
        ):
            assert (
                esolangs.run(REFERENCE, ",.", stdin=stdin, limits=limits).output == "A"
            )


@pytest.mark.parametrize("normalize", [False, True])
def test_text_export_uses_gzip_flag_for_every_container(
    tmp_path: Path, *, normalize: bool
) -> None:
    text = "+.\r\n"
    expected = (text + ("\n" if normalize else "")).encode()
    compressed = esolangs.CompressedText.from_chunks((text,))
    api = esolangs.Language(REFERENCE)
    artifact = api.from_source(compressed)
    assert artifact.source is compressed
    original, exported = tmp_path / "source.gz", tmp_path / "exported"
    original.write_bytes(compressed.to_gzip())
    for source in (text, compressed, artifact, original):
        api.to_file(source, exported, normalize=normalize)
        assert exported.read_bytes() == expected
        api.to_file(source, exported, gzip=True, normalize=normalize)
        assert gzip.decompress(exported.read_bytes()) == expected


def test_plain_export_respects_the_raw_text_budget(tmp_path: Path) -> None:
    limits = esolangs.TextLimits(plain_chars=1, generation_chars=2, gzip_bytes=100)
    compressed = esolangs.CompressedText.from_chunks(("+.",), limits=limits)
    path = tmp_path / "source"
    path.write_bytes(b"original")
    with pytest.raises(esolangs.GeneratorCapError, match="raw text"):
        esolangs.to_file(REFERENCE, compressed, path)
    assert path.read_bytes() == b"original"
    esolangs.to_file(REFERENCE, compressed, path, gzip=True)
    assert path.read_bytes() == compressed.to_gzip()


def test_native_file_terminator_counts_toward_raw_export_budget(tmp_path: Path) -> None:
    limits = esolangs.TextLimits(plain_chars=2, generation_chars=3, gzip_bytes=100)
    compressed = esolangs.CompressedText.from_chunks(("+.",), limits=limits)
    path = tmp_path / "source"
    esolangs.to_file(REFERENCE, compressed, path)
    with pytest.raises(esolangs.GeneratorCapError, match="raw text"):
        esolangs.to_file(REFERENCE, compressed, path, normalize=True)
    assert path.read_bytes() == b"+."
    esolangs.to_file(REFERENCE, compressed, path, gzip=True, normalize=True)
    assert gzip.decompress(path.read_bytes()) == b"+.\n"


@pytest.mark.parametrize("mode", ["normal", "steps", "isolated"])
def test_stream_failures_keep_public_error_types(mode: str) -> None:
    bounds: dict[str, Any] = {}
    if mode == "steps":
        bounds["limits"] = esolangs.ExecutionLimits(max_steps=100)
    elif mode == "isolated":
        bounds["isolated"] = True

    class Broken:
        def read(self) -> str:
            raise OSError("broken stream")

    class Wrong:
        def read(self) -> int:
            return 4

    class NeedsArgument:
        def read(self, _argument: int) -> str:
            return "A"

    for stream in (Broken(), Wrong(), NeedsArgument()):
        with pytest.raises(esolangs.ProgramError):
            esolangs.run(REFERENCE, stream, **bounds)
        with pytest.raises(esolangs.ArgumentError):
            esolangs.run(REFERENCE, ",.", stdin=stream, **bounds)


@pytest.mark.parametrize("blocked", ["program", "stdin"])
def test_isolated_deadline_bounds_stream_acquisition(
    blocked: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from esolangs.runtime import _isolated

    entered, release, finished = Event(), Event(), Event()

    class Stream:
        def read(self) -> str:
            entered.set()
            release.wait(5)
            finished.set()
            return ",." if blocked == "program" else "A"

    def launch(_request: str, _timeout: float) -> str:
        pytest.fail("a blocked read must time out before launching the child")

    monkeypatch.setattr(_isolated, "_launch", launch)
    program: Any = Stream() if blocked == "program" else ",."
    stdin: Any = Stream() if blocked == "stdin" else "A"
    try:
        # The execution budget bounds acquisition; a blocked stdin waited out
        # the 30-second default total instead.
        calls = {
            "stdin": lambda: esolangs.run(
                REFERENCE,
                program,
                stdin=stdin,
                limits=esolangs.ExecutionLimits(execution_timeout=0.1),
            ),
            "program": lambda: (
                esolangs.Language(REFERENCE)
                .execute(
                    program,
                    stdin=stdin,
                    isolated=True,
                    limits=esolangs.ExecutionLimits(total_timeout=0.1),
                )
                .unwrap()
            ),
        }
        with pytest.raises(esolangs.ExecutionTimeoutError, match="loading input"):
            calls[blocked]()
        assert entered.is_set()
        assert not finished.is_set()
    finally:
        release.set()
        assert finished.wait(1)
