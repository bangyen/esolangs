"""Truth-table pipes report known errors before their producer closes."""

import subprocess
import sys

import pytest

import esolangs
from esolangs.cli._table_input import _TruthTablePipeCheck
from tests.support.pick import first
from tests.support.reference import REFERENCE
from tests.tooling.script_support import REPO_ROOT


@pytest.mark.parametrize(
    ("args", "payload", "diagnostic"),
    [
        (
            ["-m", "esolangs", "generate", REFERENCE, "-"],
            b"\t01X",
            b"'X' at position 2",
        ),
        (["-m", "esolangs", "generate", REFERENCE, "-"], b"01\xff", b"not text"),
        (["-m", "esolangs", "generate", REFERENCE, "-"], b"01 0", b"' ' at position 2"),
        (
            [
                str(REPO_ROOT / "scripts/benchmark.py"),
                REFERENCE,
                "-",
                "--total-timeout",
                "4",
            ],
            b"01X",
            b"'X' at position 2",
        ),
    ],
)
def test_bad_piped_table_exits_before_eof(args, payload, diagnostic) -> None:
    _assert_pipe_rejection(args, payload, diagnostic)


def _assert_pipe_rejection(args: list[str], payload: bytes, diagnostic: bytes) -> None:
    with subprocess.Popen(
        [sys.executable, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as child:
        assert child.stdin is not None
        assert child.stdout is not None
        assert child.stderr is not None
        try:
            child.stdin.write(payload)
            child.stdin.flush()
            assert child.wait(timeout=5) == 2
            assert child.stdout.read() == b""
            assert diagnostic in child.stderr.read()
        finally:
            if child.poll() is None:
                child.kill()


def test_table_pipe_keeps_one_bom_and_surrounding_unicode_space() -> None:
    table = "\ufeff\u20030110\u2003\n"
    check = _TruthTablePipeCheck(None)
    received = bytearray()
    for unit in table.encode():
        chunk = bytes([unit])
        received.extend(chunk)
        check(chunk, received)
    generated = subprocess.check_output(
        [sys.executable, "-m", "esolangs", "generate", REFERENCE, "-"],
        input=received,
        timeout=5,
    )
    for bits, expected in zip(("00", "01", "10", "11"), "0110", strict=True):
        assert esolangs.run(REFERENCE, generated, stdin=bits).output == expected


def test_template_pipe_checks_the_rows_required_by_bits() -> None:
    name = first(parameterized=True, answer_mode="output", width_effect="wrap")
    args = ["-m", "esolangs", "generate", "--bits", "01", name, "-"]
    _assert_pipe_rejection(args, b"\t01100", b"exceeds the 4 rows required by --bits")
    generated = subprocess.check_output(
        [sys.executable, *args],
        input=b"\t0110 \n",
        timeout=5,
    )
    result = esolangs.run(name, generated)
    assert esolangs.read_answer(name, result.output) == "1"
