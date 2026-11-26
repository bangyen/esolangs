"""Execution keeps the same behavior across source and input containers."""

import base64
import errno
import gzip
import io
import json
import os
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread, current_thread
from typing import Any

import pytest

import esolangs
from esolangs.debugger import make_debugger
from esolangs.registry import LANGUAGES
from esolangs.runtime._artifact_source import check_program
from tests.support.cli_support import _failure
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
    assert check_program(REFERENCE, program, stdin).source == ",.,."
    assert stdin.reads == 0
    assert esolangs.run(REFERENCE, ",.,.", stdin=stdin).output == "\n\x00"
    assert (program.reads, stdin.reads) == (1, 1)
    source = io.StringIO("ignored,.")
    source.seek(7)
    assert esolangs.run(REFERENCE, source, stdin="Z").output == "Z"


def test_managed_program_selects_the_read_descriptor_once() -> None:
    class Stream:
        lookups = 0
        reads = 0

        @property
        def read(self):
            self.lookups += 1
            source = "+." if self.lookups == 1 else "++."

            def snapshot() -> str:
                self.reads += 1
                return source

            return snapshot

    api = esolangs.Language(REFERENCE)
    for run in (
        api.run,
        lambda stream: api.prepare(stream).run(),
        lambda stream: api.run(api.from_json(api.to_json(stream))),
    ):
        stream = Stream()
        assert run(stream).output == "\x01"
        assert (stream.lookups, stream.reads) == (1, 1)


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX nonblocking pipes")
def test_nonblocking_raw_program_waits_for_a_delayed_suffix() -> None:
    prefix_read = Event()

    class ProgramReader(io.FileIO):
        def read(self, size=-1):
            chunk = super().read(size)
            if chunk == b"+":
                prefix_read.set()
            return chunk

    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, False)
    os.write(write_fd, b"+")

    def publish_suffix() -> None:
        try:
            if prefix_read.wait(2):
                os.write(write_fd, b".")
        finally:
            os.close(write_fd)

    sender = Thread(target=publish_suffix)
    sender.start()
    try:
        with ProgramReader(read_fd, mode="rb") as stream:
            api = esolangs.Language(REFERENCE)
            artifact = api.from_json(api.to_json(stream))
            assert artifact.source == "+."
            assert api.run(artifact).output == "\x01"
            assert not stream.closed
            assert not os.get_blocking(read_fd)
    finally:
        sender.join(3)


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX nonblocking pipes")
def test_nonblocking_text_program_refuses_before_consuming_bytes() -> None:
    read_fd, write_fd = os.pipe()
    try:
        os.set_blocking(read_fd, False)
        os.write(write_fd, b"+.")
        with os.fdopen(read_fd, "r") as stream:
            with pytest.raises(
                esolangs.ProgramError, match=r"cannot detect EOF.*nonblocking"
            ):
                esolangs.run(REFERENCE, stream)
            assert os.read(read_fd, 2) == b"+."
            assert not stream.closed
    finally:
        os.close(write_fd)


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX nonblocking pipes")
def test_nonblocking_buffered_program_preserves_prefetched_bytes() -> None:
    read_fd, write_fd = os.pipe()
    with os.fdopen(read_fd, "rb") as stream:
        with os.fdopen(write_fd, "wb") as sender:
            os.set_blocking(read_fd, False)
            sender.write(b"+.")
        assert stream.peek(1) == b"+."
        assert esolangs.run(REFERENCE, stream).output == "\x01"
        assert not stream.closed


def test_closed_and_would_block_streams_report_read_errors() -> None:
    class Pending:
        def read(self):
            return None

    closed = io.BytesIO(b"+.")
    closed.close()
    for source, message in ((closed, "closed"), (Pending(), "would block")):
        with pytest.raises(
            esolangs.ProgramError, match=f"cannot read the program stream.*{message}"
        ):
            esolangs.prepare(REFERENCE, source)


@pytest.mark.parametrize(
    "error_type", [esolangs.ExecutionTimeoutError, esolangs.ArgumentError]
)
@pytest.mark.parametrize("lookup", [False, True])
def test_managed_program_stream_preserves_a_deliberate_api_error(
    error_type: type[esolangs.EsolangError], tmp_path: Path, *, lookup: bool
) -> None:
    error = error_type("managed read failed")
    bound = None
    if isinstance(error, esolangs.ExecutionTimeoutError):
        error.bound = bound = "preparation_timeout"

    class Stream:
        @property
        def read(self):
            if lookup:
                raise error
            return self._read

        def _read(self):
            raise error

    class RefusedDescriptor(io.BytesIO):
        def fileno(self):
            raise error

    api = esolangs.Language(REFERENCE)
    prepared = api.prepare(",.")
    for limits in (
        None,
        esolangs.ExecutionLimits(max_steps=2),
        esolangs.ExecutionLimits(total_timeout=5),
    ):
        for source in (Stream(), RefusedDescriptor(b",.")):
            stdin = io.StringIO("A")
            outcome = api.execute(source, stdin=stdin, limits=limits)
            assert outcome.error is error
            assert outcome.bound == bound
            assert stdin.tell() == 0
            if isinstance(source, RefusedDescriptor):
                assert source.tell() == 0
        native_stdin = RefusedDescriptor(b"A")
        prepared_stdin = RefusedDescriptor(b"A")
        for outcome in (
            api.execute(",.", stdin=native_stdin, limits=limits),
            prepared.execute(stdin=prepared_stdin, limits=limits),
        ):
            assert outcome.error is error
            assert outcome.bound == bound
        assert native_stdin.tell() == prepared_stdin.tell() == 0
    path = tmp_path / "source"
    path.write_bytes(b"existing source")
    for source in (Stream(), RefusedDescriptor(b",.")):
        for acquire in (
            api.prepare,
            api.make_debugger,
            api.to_json,
            lambda source: api.to_file(source, path),
        ):
            with pytest.raises(error_type) as raised:
                acquire(source)
            assert raised.value is error
        if isinstance(source, RefusedDescriptor):
            assert source.tell() == 0
    assert path.read_bytes() == b"existing source"
    assert api.run(io.BytesIO(b",."), stdin=io.BytesIO(b"A")).output == "A"


@pytest.mark.parametrize(
    "stdin", ["é", "é".encode(), io.StringIO("é"), io.BytesIO("é".encode())]
)
def test_binary_stdin_uses_the_same_unicode_character_stream(stdin: Any) -> None:
    assert esolangs.run(REFERENCE, ",.", stdin=stdin).output == "é"


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX path semantics")
@pytest.mark.parametrize("suffix", ["/", "/."])
def test_native_file_operations_keep_directory_qualified_spellings(
    tmp_path: Path, suffix: str
) -> None:
    class FileName:
        def __init__(self, spelling: str) -> None:
            self.spelling = spelling
            self.calls = 0

        def __fspath__(self) -> str:
            self.calls += 1
            return self.spelling

    source = tmp_path / "source\x1b[2J\n"
    source.write_bytes(b"+.")
    api = esolangs.Language(REFERENCE)
    assert api.from_file(source).source == "+."
    spelling = str(source) + suffix
    label = repr(spelling)[1:-1]
    exact = FileName(spelling)
    for load in (lambda: api.from_file(spelling), lambda: api.prepare(exact)):
        with pytest.raises(esolangs.ProgramError, match="Not a directory") as caught:
            load()
        assert label in str(caught.value)
    assert exact.calls == 1

    compressed = esolangs.CompressedText.from_chunks(("++.",))
    for save in (
        lambda target: api.to_file("++.", target),
        lambda target: api.to_file(io.BytesIO(b"++."), target),
        compressed.to_file,
    ):
        for target in (spelling, FileName(spelling)):
            with pytest.raises(esolangs.ProgramError, match="cannot save") as caught:
                save(target)
            message = str(caught.value)
            assert message.startswith(f"cannot save program to {label}:")
            assert "\x1b" not in message
            assert "\n" not in message
            assert isinstance(caught.value.__cause__, OSError)
            if isinstance(target, FileName):
                assert target.calls == 1
        assert source.read_bytes() == b"+."
    assert list(tmp_path.iterdir()) == [source]


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
    assert check_program(REFERENCE, path).source == "+,\r\n.\r\n"
    assert esolangs.run(REFERENCE, path, stdin="Q").output == "Q"

    for raw, changes in ((b"+,\n.", False), (path.read_bytes(), True)):
        output = io.BytesIO()
        with gzip.GzipFile("original.bf", "wb", fileobj=output, mtime=123) as archive:
            archive.write(raw)
        data = output.getvalue()
        path.write_bytes(data)
        artifact = api.from_file(path, normalize=True)
        expected = "+,\n." if changes else esolangs.CompressedText(data)
        assert artifact == api.from_source(expected)
        document = api.to_json(artifact)
        assert json.loads(document)["kind"] == ("text" if changes else "gzip")
        restored = api.from_json(document)
        assert restored == artifact
        assert api.run(restored, stdin="Q").output == "Q"
        api.to_file(restored, path, gzip=True)
        assert gzip.decompress(path.read_bytes()) == b"+,\n."
        if not changes:
            assert path.read_bytes() == data


@pytest.mark.parametrize(
    ("data", "message", "hint"),
    [
        (
            gzip.compress(b"+.\xff", mtime=0),
            "invalid UTF-8 at decoded byte 2",
            "save the text program as UTF-8",
        ),
        (
            gzip.compress(b"+.", mtime=0)[:-1],
            "truncated gzip source",
            "complete gzip file",
        ),
        (
            gzip.compress(b"+.", mtime=0)[:-8] + bytes(8),
            "CRC check failed",
            "valid gzip file",
        ),
    ],
    ids=["invalid-utf8", "truncated", "crc"],
)
def test_gzip_diagnostics_keep_filename_and_repair_hint(
    data: bytes, message: str, hint: str, tmp_path: Path, capsys
) -> None:
    api = esolangs.Language(REFERENCE)
    path = tmp_path / "source"
    path.write_bytes(data)
    for acquire in (
        api.from_file,
        api.prepare,
        api.to_json,
        lambda path: api.run(path, isolated=True),
    ):
        with pytest.raises(esolangs.ProgramError, match=message) as caught:
            acquire(path)
        assert str(path) in str(caught.value)
        assert any(hint in note for note in caught.value.__notes__)
    _, stderr = _failure(["run", REFERENCE, str(path)], capsys)
    assert str(path) in stderr
    assert message in stderr
    assert hint in stderr

    valid = gzip.compress(b"+.", mtime=0)
    document = json.loads(api.to_json(valid))
    document["source"] = base64.b64encode(data).decode("ascii")
    with pytest.raises(esolangs.ProgramError, match=message) as caught:
        api.from_json(json.dumps(document))
    assert any(hint in note for note in caught.value.__notes__)
    path.write_bytes(valid)
    assert api.prepare(path).run().output == "\x01"


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


def test_explicit_paths_are_validated_on_import_and_export() -> None:
    class BadPath:
        def __init__(self, spelling: object) -> None:
            self.spelling = spelling

        def __fspath__(self) -> object:
            if isinstance(self.spelling, Exception):
                raise self.spelling
            return self.spelling

    compressed = esolangs.CompressedText.from_chunks(("+.",))
    spellings = ("", b"bytes", 1, TypeError("bad path"))
    for path in ("", *map(BadPath, spellings)):
        with pytest.raises(esolangs.ArgumentError, match="path"):
            esolangs.from_file(REFERENCE, path)
        with pytest.raises(esolangs.ArgumentError, match="path"):
            esolangs.to_file(REFERENCE, "+.", path)
        with pytest.raises(esolangs.ProgramError, match="path") as caught:
            compressed.to_file(path)
        assert isinstance(caught.value.__cause__, esolangs.ArgumentError)


@pytest.mark.parametrize("failure", [FileNotFoundError, PermissionError])
def test_path_provider_io_errors_match_the_file_operation(
    failure: type[OSError], tmp_path: Path
) -> None:
    pointer = tmp_path / "pointer"

    class ReferencedPath:
        calls = 0

        def __fspath__(self) -> str:
            self.calls += 1
            if failure is PermissionError and not pointer.exists():
                raise PermissionError(errno.EACCES, "path unreadable", pointer)
            return pointer.read_text(encoding="utf-8")

    api = esolangs.Language(REFERENCE)
    compressed = esolangs.CompressedText.from_chunks((",.",))
    source = io.BytesIO(b"skip,.")
    source.seek(4)
    error_type = (
        esolangs.ProgramNotFoundError
        if failure is FileNotFoundError
        else esolangs.ProgramError
    )
    for operation, expected in (
        (api.from_file, error_type),
        (api.prepare, error_type),
        (lambda path: api.to_file(source, path), esolangs.ProgramError),
        (compressed.to_file, esolangs.ProgramError),
    ):
        provider = ReferencedPath()
        with pytest.raises(expected) as caught:
            operation(provider)
        assert type(caught.value) is expected
        assert type(caught.value.__cause__) is failure
        assert provider.calls == 1
    assert source.tell() == 4

    destination = tmp_path / "destination"
    pointer.write_text(str(destination), encoding="utf-8")
    provider = ReferencedPath()
    api.to_file(source, provider)
    assert provider.calls == 1
    assert api.run(api.from_file(provider), stdin="Q").output == "Q"
    assert provider.calls == 2
    compressed.to_file(provider)
    assert provider.calls == 3
    assert api.from_file(destination).source == compressed


def test_managed_path_preserves_deliberate_errors_and_own_observations(
    tmp_path: Path,
) -> None:
    api = esolangs.Language(REFERENCE)
    nested = api.execute("+.[+]", limits=esolangs.ExecutionLimits(max_steps=2))
    assert nested.observation.output == "\x01"
    with pytest.raises(esolangs.ProgramNotFoundError) as missing:
        api.from_file(tmp_path / "missing")
    timeout = esolangs.ExecutionTimeoutError("managed path timed out")
    timeout.bound = "preparation_timeout"
    errors = (missing.value, esolangs.ArgumentError("managed argument"), timeout)

    class ManagedPath:
        calls = 0

        def __init__(self, failure: esolangs.EsolangError) -> None:
            self.failure = failure

        def __fspath__(self) -> str:
            self.calls += 1
            raise self.failure

    source = io.BytesIO(b",.")
    destination = tmp_path / "destination"
    compressed = esolangs.CompressedText.from_chunks((",.",))
    for error in errors:
        error.observation = nested.observation
        error.partial_output = nested.observation.output
        for isolated in (False, True):
            provider = ManagedPath(error)
            stdin = io.BytesIO(b"Q")
            outcome = api.execute(provider, stdin=stdin, isolated=isolated)
            assert outcome.error is error
            assert outcome.status == ("limit" if error is timeout else "rejected")
            assert outcome.bound == (timeout.bound if error is timeout else None)
            assert outcome.observation == esolangs.ExecutionResult("", None, None, None)
            assert stdin.tell() == 0
            assert provider.calls == 1
        for accept in (
            api.prepare,
            api.make_debugger,
            api.from_file,
            api.to_json,
            lambda provider: api.to_file(provider, destination),
            lambda provider: api.to_file(source, provider),
            compressed.to_file,
        ):
            provider = ManagedPath(error)
            with pytest.raises(type(error)) as caught:
                accept(provider)
            assert caught.value is error
            assert provider.calls == 1
        assert error.observation is nested.observation
        assert error.partial_output == "\x01"
    assert source.tell() == 0
    assert not destination.exists()
    api.to_file(source, destination)
    assert api.run(destination, stdin="Q").output == "Q"


@pytest.mark.parametrize(
    ("spelling", "message"),
    [
        (".", "it is a directory"),
        ("missing/program", "directory does not exist"),
        pytest.param("nul\0target", "embedded null", id="embedded-null"),
    ],
)
def test_invalid_export_destination_does_not_consume_source(
    spelling: str, message: str, tmp_path: Path
) -> None:
    api = esolangs.Language(REFERENCE)
    source = io.BytesIO(b"skip+.")
    source.seek(4)
    with pytest.raises(
        esolangs.ArgumentError, match="settings must be a DialectSettings"
    ):
        api.to_file(source, tmp_path / spelling, settings=object())
    with pytest.raises(esolangs.ProgramError, match=message):
        api.to_file(source, tmp_path / spelling)
    assert source.tell() == 4
    destination = tmp_path / "program"
    api.to_file(source, destination)
    assert destination.read_bytes() == b"+."
    assert api.run(destination).output == "\x01"


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX filename limits")
def test_export_preserves_destination_errors_without_consuming_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    limit = os.pathconf(tmp_path, "PC_NAME_MAX")
    if limit < 1:
        pytest.skip("filesystem does not specify a filename limit")
    monkeypatch.chdir(tmp_path)
    source = io.BytesIO(b"skip+.")
    source.seek(4)
    api = esolangs.Language(REFERENCE)

    Path("file").touch()
    Path("loop").symlink_to("loop")
    overlong = "x" * (limit + 1)
    compressed = esolangs.CompressedText.from_chunks(("+.",))
    for path, problem in (
        (overlong, errno.ENAMETOOLONG),
        (f"{overlong}/program", errno.ENAMETOOLONG),
        ("file/program", errno.ENOTDIR),
        ("loop/program", errno.ELOOP),
    ):
        for save in (lambda path: api.to_file(source, path), compressed.to_file):
            with pytest.raises(esolangs.ProgramError, match="cannot save") as caught:
                save(path)
            cause = caught.value.__cause__
            assert isinstance(cause, OSError)
            assert cause.errno == problem
        assert source.tell() == 4

    destination = "x" * limit
    api.to_file(source, destination)
    assert Path(destination).read_bytes() == b"+."
    assert api.run(Path(destination)).output == "\x01"


@pytest.mark.parametrize(
    "spelling",
    [
        "relative",
        pytest.param(
            "drive-relative",
            marks=pytest.mark.skipif(os.name != "nt", reason="requires Windows drives"),
        ),
    ],
)
def test_export_anchors_relative_destination_before_callbacks(
    spelling: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caller, other = tmp_path / "caller", tmp_path / "other"
    caller.mkdir()
    other.mkdir()
    destination, unrelated = caller / "program", other / "program"
    destination.write_bytes(b"++.")
    unrelated.write_bytes(b"+++.")
    monkeypatch.chdir(caller)

    class Source(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            os.chdir(other)
            return super().read(size)

    target = f"{caller.drive}program" if spelling == "drive-relative" else "program"
    api = esolangs.Language(REFERENCE)
    api.to_file(Source(b"+."), target)
    assert destination.read_bytes() == b"+."
    assert unrelated.read_bytes() == b"+++."
    assert api.run(destination).output == "\x01"

    class Destination(os.PathLike[str]):
        def __init__(self, path: str) -> None:
            self.path = path
            self.calls = 0

        def __fspath__(self) -> str:
            self.calls += 1
            os.chdir(other)
            return self.path

    compressed = esolangs.CompressedText.from_chunks(["+."])
    for name in (target, str(destination)):
        for archive in (False, True):
            monkeypatch.chdir(caller)
            destination.write_bytes(b"++.")
            provider = Destination(name)
            if archive:
                compressed.to_file(provider)
                assert destination.read_bytes() == compressed.to_gzip()
            else:
                api.to_file("+.", provider)
                assert destination.read_bytes() == b"+."
            assert provider.calls == 1
            assert Path.cwd().samefile(other)
            assert unrelated.read_bytes() == b"+++."
            assert api.run(destination).output == "\x01"

    declaration = LANGUAGES[REFERENCE]
    schema = esolangs.DialectSchema(
        REFERENCE, {"mode": ("hold", "move")}, {"mode": "hold"}
    )
    relocate = False

    def validate(mode="hold"):
        if mode == "move" and relocate:
            os.chdir(other)

    runtime = replace(declaration.runtime, dialect=validate, dialect_schema=schema)
    scoped = esolangs.Catalog([replace(declaration, runtime=runtime)]).bind(REFERENCE)
    settings = scoped.settings(mode="move")
    relocate = True
    for program, path in (
        ("+.", target),
        (api.from_source("+."), target),
        (io.BytesIO(b"+."), target),
        ("+.", destination),
    ):
        monkeypatch.chdir(caller)
        destination.write_bytes(b"++.")
        scoped.to_file(program, path, settings=settings)
        assert Path.cwd().samefile(other)
        assert destination.read_bytes() == b"+."
        assert unrelated.read_bytes() == b"+++."
        assert api.run(destination).output == "\x01"

    monkeypatch.chdir(caller)
    with pytest.raises(
        esolangs.ProgramError, match=r"cannot save program to missing/program:"
    ):
        scoped.to_file("+.", "missing/program", settings=settings)


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX directory modes")
def test_unwritable_export_directory_does_not_consume_source(tmp_path: Path) -> None:
    api = esolangs.Language(REFERENCE)
    parent = tmp_path / "export"
    parent.mkdir()
    destination = parent / "program"
    source = io.BytesIO(b"skip+.")
    source.seek(4)
    try:
        for mode, denied in ((0o555, destination), (0, parent / "nested" / "program")):
            parent.chmod(mode)
            if os.access(parent, os.W_OK if mode else os.X_OK):
                pytest.skip("filesystem does not enforce the test directory modes")
            with pytest.raises(esolangs.ProgramError, match="cannot save") as caught:
                api.to_file(source, denied)
            assert isinstance(caught.value.__cause__, PermissionError)
            assert source.tell() == 4
    finally:
        parent.chmod(0o755)
    assert list(parent.iterdir()) == []
    api.to_file(source, destination)
    assert list(parent.iterdir()) == [destination]
    assert destination.read_bytes() == b"+."
    assert api.run(destination).output == "\x01"


@pytest.mark.parametrize(
    ("payload", "message"),
    [(b"\xff", "invalid UTF-8"), ("\ud800", "cannot save")],
)
def test_stream_export_failure_cleans_reserved_file(
    payload: str | bytes, message: str, tmp_path: Path
) -> None:
    api = esolangs.Language(REFERENCE)
    destination = tmp_path / "program"
    destination.write_bytes(b"+.")

    class Source:
        def read(self) -> str | bytes:
            assert len(list(tmp_path.glob("*/source"))) == 1
            return payload

    with pytest.raises(esolangs.ProgramError, match=message):
        api.to_file(Source(), destination)
    assert list(tmp_path.iterdir()) == [destination]
    assert destination.read_bytes() == b"+."


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX directory modes")
@pytest.mark.parametrize("source_refused", [True, False], ids=["read-error", "saved"])
def test_stream_export_retains_error_when_staging_cleanup_is_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, source_refused: bool
) -> None:
    api = esolangs.Language(REFERENCE)
    parent = tmp_path / "export"
    parent.mkdir()
    parent.chmod(0o555)
    try:
        if os.access(parent, os.W_OK):
            pytest.skip("filesystem or current user can write read-only directories")
    finally:
        parent.chmod(0o755)
    destination = parent / "program"
    read_error = esolangs.ProgramError("reader refused")

    class Source:
        def read(self) -> bytes:
            if source_refused:
                parent.chmod(0o555)
                raise read_error
            return b"+."

    if not source_refused:
        replace_path = os.replace

        def replace_and_restrict(path, target, **directories) -> None:
            replace_path(path, target, **directories)
            parent.chmod(0o555)

        monkeypatch.setattr(os, "replace", replace_and_restrict)

    try:
        with pytest.raises(esolangs.ProgramError) as caught:
            api.to_file(Source(), destination)
    finally:
        parent.chmod(0o755)
        (staging,) = (entry for entry in parent.iterdir() if entry != destination)
        staging.rmdir()
    if source_refused:
        assert caught.value is read_error
        assert any("could not clean staging" in note for note in read_error.__notes__)
        assert not destination.exists()
    else:
        assert "cannot save program" in str(caught.value)
        assert isinstance(caught.value.__cause__, PermissionError)
        assert api.run(destination).output == "\x01"


def test_invalid_export_destination_does_not_open_source_path(tmp_path: Path) -> None:
    original = tmp_path / "original"
    original.write_bytes(b"+.")

    class SourcePath:
        calls = 0

        def __fspath__(self) -> str:
            self.calls += 1
            return str(original)

    api = esolangs.Language(REFERENCE)
    source = SourcePath()
    with pytest.raises(esolangs.ProgramError, match="it is a directory"):
        api.to_file(source, tmp_path)
    assert source.calls == 0
    destination = tmp_path / "program"
    api.to_file(source, destination)
    assert source.calls == 1
    assert destination.read_bytes() == b"+."


def test_gzip_raster_export_refuses_before_consuming_source(tmp_path: Path) -> None:
    api = esolangs.Language(_RASTERS[0])
    pixels = esolangs.Raster((((1, 2, 3),),))
    source = io.BytesIO(pixels.to_png())
    destination = tmp_path / "source.png"
    with pytest.raises(esolangs.ProgramError, match="rasters use PNG"):
        api.to_file(source, destination, gzip=True)
    assert source.tell() == 0
    assert not destination.exists()
    api.to_file(source, destination)
    assert api.from_file(destination).source == pixels


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


class _ClaimedContainer:
    def __init__(self, claimed: type) -> None:
        self.claimed = claimed
        self.probes = 0

    @property
    def __class__(self) -> type:
        self.probes += 1
        return self.claimed


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
    for claimed in (str, bytes, esolangs.ProgramArtifact):
        fake = _ClaimedContainer(claimed)
        for limits in (None, esolangs.ExecutionLimits(total_timeout=5)):
            for source in (fake, Stream(fake)):
                result = api.execute(source, limits=limits)
                assert result.status == "rejected"
                assert type(result.error) is esolangs.ProgramError
                assert "program must be" in str(result.error)
        assert fake.probes == 0


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

    class Stream:
        def __init__(self, value: object) -> None:
            self.value = value

        def read(self) -> object:
            return self.value

    for claimed in (str, bytes):
        fake = _ClaimedContainer(claimed)
        for limits in (
            None,
            esolangs.ExecutionLimits(max_steps=10),
            esolangs.ExecutionLimits(total_timeout=5),
        ):
            for source in (fake, Stream(fake)):
                result = esolangs.execute(REFERENCE, ",.", stdin=source, limits=limits)
                assert result.status == "rejected"
                assert type(result.error) is esolangs.ArgumentError
                assert "stdin" in str(result.error)
        assert fake.probes == 0


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
    if blocked == "program":
        _check_timed_source_binding_stops_before_descriptor_probe()


def _check_timed_source_binding_stops_before_descriptor_probe() -> None:
    release = Event()
    threads: list[Thread] = []
    probes: list[str] = []

    class DeferredReader(io.BytesIO):
        @property
        def read(self):
            threads.append(current_thread())
            assert release.wait(5)
            return super().read

        def fileno(self):
            probes.append("fileno")
            return super().fileno()

    source = DeferredReader(b"+.")
    try:
        outcome = esolangs.Language(REFERENCE).execute(
            source,
            limits=esolangs.ExecutionLimits(preparation_timeout=0.1, total_timeout=1),
        )
        assert outcome.status == "limit"
        assert outcome.bound == "preparation_timeout"
        assert len(threads) == 1
        assert source.tell() == 0
    finally:
        release.set()
        for thread in threads:
            thread.join(1)
            assert not thread.is_alive()
    assert probes == []
    assert source.tell() == 0
