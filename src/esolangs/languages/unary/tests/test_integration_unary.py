"""Unary through the shared API and generator contract."""

import gzip
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Event, current_thread
from time import monotonic

import pytest

import esolangs
from esolangs import run
from esolangs.runtime._files import StreamReadTimeoutError, stream_read_deadline
from esolangs.runtime._source import _native_compressed_source
from tests.support.cli_support import call_main


def test_describe_writes_no_raw_nul(capsys: pytest.CaptureFixture[str]) -> None:
    """Its zero bit is NUL; ``describe`` wrote it raw into the input line."""
    out = call_main(["describe", "Unary"], capsys)
    assert "\x00" not in out
    assert "\\x00" in out.splitlines()[1]


def test_unary_generator_declares_byte_inputs_and_termination_answers() -> None:
    description = esolangs.describe("Unary")
    assert description.input_encoding == ("\x00", "\xff")
    assert description.answer_mode == "termination"
    assert esolangs.encode_inputs("Unary", (0, 1)) == "\x00\xff"
    assert len(esolangs.generate("Unary", "01").source) == 887


def test_compressed_and_plain_sources_share_execution(tmp_path, monkeypatch) -> None:
    program = esolangs.generate("Unary", "0001")
    assert isinstance(program.source, esolangs.CompressedText)
    assert len(program.source) == 27_452_351
    assert len(program.source.to_gzip()) == 26_712
    path = tmp_path / "and.txt.gz"
    esolangs.to_file("Unary", program, path)
    for source in (program, program.source.to_gzip(), path, str(program.source)):
        assert (
            run(
                "Unary",
                source,
                stdin="\x00\xff",
                limits=esolangs.ExecutionLimits(max_steps=20),
            ).output
            == ""
        )
    restored = esolangs.from_json("Unary", esolangs.to_json("Unary", program))
    assert isinstance(restored, esolangs.ProgramArtifact)
    assert isinstance(restored.source, esolangs.CompressedText)
    assert restored == program
    assert (
        run(
            "Unary",
            program,
            stdin="\x00\xff",
            isolated=True,
            limits=esolangs.ExecutionLimits(execution_timeout=5),
        ).output
        == ""
    )
    _check_normalized_gzip_storage(path)
    _check_expired_gzip_acquisition(path, monkeypatch)


def _check_normalized_gzip_storage(path) -> None:
    api = esolangs.Language("Unary")
    code = str(api.generate("01").source)
    limits = esolangs.ExecutionLimits(max_steps=20)
    for text, canonical in (
        (code, code),
        (code[:100] + "\r" + code[100:], code[:100] + "\n" + code[100:]),
        (code + "\r\n", code),
    ):
        data = gzip.compress(text.encode(), mtime=123)
        path.write_bytes(data)
        restored = api.from_file(path, normalize=True)
        assert gzip.decompress(restored.source.to_gzip()).decode() == canonical
        assert (restored.source.to_gzip() == data) is (text == canonical)
        checked = api.from_json(api.to_json(restored))
        assert checked == restored
        assert (
            "".join(
                api.evaluate(checked, [bit], limits=limits).answer for bit in (0, 1)
            )
            == "01"
        )

        budgets = esolangs.TextLimits(
            plain_chars=0, generation_chars=len(text), gzip_bytes=len(data) + 5
        )
        source = esolangs.CompressedText(data, limits=budgets)
        normalized = _native_compressed_source(source)
        assert normalized == esolangs.CompressedText(
            restored.source.to_gzip(), limits=budgets
        )
        assert (normalized is source) is (text == canonical)
        with pytest.raises(esolangs.GeneratorCapError, match="raw text"):
            str(normalized)


def _check_expired_gzip_acquisition(path, monkeypatch) -> None:
    api = esolangs.Language("Unary")
    plain = str(api.generate("01").source).encode() + b" " * (3 * 65_536)
    data = gzip.compress(plain, mtime=0)
    path.write_bytes(data)

    stdin = BytesIO(b"\0")
    paused, resume = Event(), Event()
    reads = []
    original_read = gzip.GzipFile.read

    def pause_first_read(stream, size=-1):
        reads.append(current_thread())
        if len(reads) == 1:
            paused.set()
            assert resume.wait(5)
        return original_read(stream, size)

    with monkeypatch.context() as edit, ThreadPoolExecutor() as callers:
        edit.setattr(gzip.GzipFile, "read", pause_first_read)
        pending = callers.submit(
            api.execute,
            path,
            stdin=stdin,
            isolated=True,
            limits=esolangs.ExecutionLimits(preparation_timeout=0.5, total_timeout=5),
        )
        try:
            assert paused.wait(2)
            outcome = pending.result(timeout=3)
            assert outcome.status == "limit"
            assert outcome.bound == "preparation_timeout"
            assert stdin.tell() == 0
        finally:
            resume.set()
        reads[0].join(2)
        assert not reads[0].is_alive()
    assert len(reads) == 1
    with stream_read_deadline(monotonic() - 1), pytest.raises(StreamReadTimeoutError):
        esolangs.CompressedText(data)
    retry = api.run(path, stdin=stdin, limits=esolangs.ExecutionLimits(max_steps=20))
    assert (retry.output, retry.steps, stdin.tell()) == ("", 2, 1)


def test_cli_exports_gzip_by_default_and_plain_on_request(tmp_path) -> None:
    import subprocess
    import sys

    command = [sys.executable, "-m", "esolangs", "generate", "Unary", "01"]
    options = {"capture_output": True, "timeout": 10}
    packed = subprocess.run(command, check=True, **options)
    explicit = subprocess.run([*command, "--gzip"], check=True, **options)
    plain = subprocess.run([*command, "--plain"], check=True, **options)
    source = esolangs.generate("Unary", "01").source
    assert isinstance(source, esolangs.CompressedText)
    assert packed.stdout == explicit.stdout == source.to_gzip()
    assert str(esolangs.CompressedText(packed.stdout)) == "0" * 887
    assert plain.stdout == b"0" * 887
    path = tmp_path / "source.txt.gz"
    module = esolangs.registry.INTERPRETERS["Unary"]
    for body in (packed.stdout, plain.stdout):
        path.write_bytes(body)
        native = subprocess.run(
            [sys.executable, "-m", module, str(path)],
            input=b"\0",
            check=True,
            **options,
        )
        assert native.stdout == b"Input: "

    api = esolangs.Language("Unary")
    wrapped = api.generate("01", width=887)
    assert str(wrapped.source) == "0" * 887 + "\n"
    limits = esolangs.ExecutionLimits(max_steps=20)
    expected = api.run(wrapped, stdin="\0", limits=limits)
    assert (expected.output, expected.steps) == ("", 2)
    for flags in ([], ["--plain"]):
        export = subprocess.run(
            [*command, "--width=887", *flags], check=True, **options
        )
        data = export.stdout
        assert (data if flags else gzip.decompress(data)) == b"0" * 887 + b"\n\n"
        path.write_bytes(data)
        assert str(api.from_file(path, normalize=True).source) == str(wrapped.source)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "esolangs",
                "run",
                "--max-steps=20",
                "Unary",
                str(path),
            ],
            input=b"\0",
            check=True,
            **options,
        )
        assert (result.stdout, result.stderr) == (expected.output.encode(), b"")

    note = f"note: {path} contains no source, so there was no program to run\n"
    for source, expected, diagnostic in (
        (b"", b"", note.encode()),
        (b" ", b"", b""),
        (b"0" * 84, b"\x01", b""),
    ):
        for body in (source, gzip.compress(source, mtime=0)):
            path.write_bytes(body)
            result = subprocess.run(
                [sys.executable, "-m", "esolangs", "run", "Unary", str(path)],
                input=b"",
                check=True,
                **options,
            )
            assert result.stdout == expected
            assert result.stderr == diagnostic


@pytest.mark.medium
def test_cli_loads_its_large_plain_export(tmp_path) -> None:
    import subprocess
    import sys

    command = [sys.executable, "-m", "esolangs"]
    path = tmp_path / "plain.txt"
    with path.open("wb") as destination:
        subprocess.run(
            [*command, "generate", "--plain", "Unary", "0001"],
            stdout=destination,
            check=True,
            timeout=10,
        )
    assert path.stat().st_size > 1024 * 1024
    stdin = esolangs.encode_inputs("Unary", [0, 1]).encode()
    result = subprocess.run(
        [*command, "run", "--max-steps", "20", "unary", str(path)],
        input=stdin,
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert result.stdout == result.stderr == b""
