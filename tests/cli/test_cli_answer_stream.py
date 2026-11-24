"""Bounded stdin for the CLI last-character answer contract."""

import subprocess
import sys

import pytest

from esolangs.cli import _answer_input, main
from tests.support.reference import REFERENCE


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


def test_read_answer_rejects_invalid_utf8_before_pipe_eof():
    with subprocess.Popen(
        [sys.executable, "-m", "esolangs", "read-answer", REFERENCE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        assert child.stdin is not None
        assert child.stdout is not None
        assert child.stderr is not None
        try:
            child.stdin.write(b"1\xff")
            child.stdin.flush()
            assert child.wait(timeout=5) == 2
            assert child.stdout.read() == b""
            assert b"invalid UTF-8 at byte 1" in child.stderr.read()
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
