"""Stream CLI answers and preserve EOF and encoding behavior."""

import subprocess
import sys

import pytest

import esolangs
from esolangs.cli import _answer_input, main
from tests.support.pick import one_where
from tests.support.reference import REFERENCE

_PATTERNED = one_where(
    lambda facts: facts.answer_pattern is not None,
    source_kind="text",
    boolean_generator=True,
)


@pytest.mark.parametrize("pipe", [False, True], ids=["file", "pipe"])
def test_read_answer_streams_across_utf8_and_whitespace_boundaries(tmp_path, pipe):
    block = _answer_input._BLOCK
    data = b"x" * (block - 1) + "\u20ac1".encode() + b" " * (block * 3) + b"\n"
    command = [sys.executable, "-m", "esolangs", "read-answer", REFERENCE]
    path = tmp_path / "result.txt"
    path.write_bytes(data)
    with path.open("rb") as stream:
        options = {"input": data} if pipe else {"stdin": stream}
        result = subprocess.run(
            command, **options, capture_output=True, timeout=10, check=False
        )
    assert (result.returncode, result.stdout, result.stderr) == (0, b"1\n", b"")


def test_read_answer_reports_absolute_byte_offset_after_streamed_prefix(tmp_path):
    block = _answer_input._BLOCK
    path = tmp_path / "result.txt"
    path.write_bytes(b"1" + b" " * (block - 2) + b"\xe2X")
    with path.open("rb") as stream:
        result = subprocess.run(
            [sys.executable, "-m", "esolangs", "read-answer", REFERENCE],
            stdin=stream,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    assert (result.returncode, result.stdout) == (2, "")
    assert f"invalid UTF-8 at byte {block - 1}" in result.stderr


@pytest.mark.parametrize(
    ("language", "prefix"),
    [(REFERENCE, b"1"), *((language, b"output") for language in _PATTERNED)],
)
def test_read_answer_rejects_invalid_utf8_before_pipe_eof(language, prefix):
    with subprocess.Popen(
        [sys.executable, "-m", "esolangs", "read-answer", language],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        assert child.stdin is not None
        assert child.stdout is not None
        assert child.stderr is not None
        try:
            child.stdin.write(prefix + b"\xff")
            child.stdin.flush()
            assert child.wait(timeout=5) == 2
            assert child.stdout.read() == b""
            assert (
                f"invalid UTF-8 at byte {len(prefix)}".encode() in child.stderr.read()
            )
        finally:
            if child.poll() is None:
                child.kill()


@pytest.mark.parametrize("language", _PATTERNED)
def test_pattern_answer_waits_for_eof(language):
    api = esolangs.Language(language)
    answer = api.evaluate(api.generate("01"), [0])
    assert answer.answer == "0"
    with subprocess.Popen(
        [sys.executable, "-m", "esolangs", "read-answer", language],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        assert child.stdin is not None
        try:
            child.stdin.write(answer.observation.output.encode("utf-8"))
            child.stdin.flush()
            with pytest.raises(subprocess.TimeoutExpired):
                child.wait(timeout=0.2)
            child.stdin.close()
            child.stdin = None
            assert child.communicate(timeout=5) == (b"0\n", b"")
            assert child.returncode == 0
        finally:
            if child.poll() is None:
                child.kill()


def test_read_answer_native_reads_request_only_one_block(tmp_path, monkeypatch, capsys):
    path = tmp_path / "result.txt"
    path.write_bytes(b"1" + b" " * (_answer_input._BLOCK * 3))
    sizes = []
    read = _answer_input._read_stdin_bytes

    def record(stream, deadline, *, size=None, pipe_check=None):
        sizes.append(size)
        return read(stream, deadline, size=size, pipe_check=pipe_check)

    monkeypatch.setattr(_answer_input, "_read_stdin_bytes", record)
    monkeypatch.setattr(sys, "argv", ["esolangs", "read-answer", REFERENCE])
    with path.open(encoding="utf-8") as stream:
        monkeypatch.setattr(sys, "stdin", stream)
        main()
    assert sizes == [_answer_input._BLOCK] * 4
    assert capsys.readouterr() == ("1\n", "")
