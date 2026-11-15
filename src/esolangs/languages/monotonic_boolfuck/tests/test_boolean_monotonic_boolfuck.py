"""Tests for the Monotonic Boolfuck Boolean generator."""

from pathlib import Path

import pytest

import esolangs
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.cli_support import call_main
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import assert_native_rows, three_input_corpus_size
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        if table == "00":
            _check_constants()
        from esolangs.languages.monotonic_boolfuck.interpreter import run

        program = esolangs.generate("Monotonic Boolfuck", table).source
        assert_native_rows("Monotonic Boolfuck", table, program, run, sentinel="Q")


def test_plain_cli_source_can_exceed_the_stream_cap(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    language = "Monotonic Boolfuck"
    table = "".join(str(row.bit_count() % 2) for row in range(16))
    source = call_main(["generate", "--plain", language, table], capsys)
    path = tmp_path / "program"
    assert path.write_text(source, encoding="utf-8") > 256
    monkeypatch.setattr("esolangs.cli.io._MAX_PROGRAM_BYTES", 256)
    for row in (0, 1):
        stdin = esolangs.encode_inputs(language, [0, 0, 0, row])
        output = call_main(["run", language, str(path)], capsys, stdin=stdin)
        assert esolangs.read_answer(language, output) == table[row]


def _check_constants() -> None:
    assert_analysis_complement("Monotonic Boolfuck", "subtree_ids")
    from esolangs.languages.monotonic_boolfuck.interpreter import _Machine

    for n in range(1, 13):
        for bit in "01":
            commands = 20 if n == 1 else 14 * n + 9 + 2 * int(bit)
            length = 20 if n == 1 else 3 * n + 19 + 2 * int(bit)
            bound = (
                13 + (length - 1).bit_length() + n.bit_length()
                if n == 1
                else 12
                + (length - 1).bit_length()
                + 2 * n.bit_length()
                + sum(i.bit_length() for i in range(1, n))
            )
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate(
                    "Monotonic Boolfuck", bit * (1 << n), **options
                ).source
                assert len("".join(program.split())) == length
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    io = ReadFirstIO(f"{row:0{n}b}" + "Q", expected=n)
                    machine = _Machine("".join(program.split()), io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(machine, commands, written=written)
                    assert (steps, written.bits) == (commands, bound)
                    assert io.getvalue() == bit
                    assert (machine.state.remaining, io.past_end) == (0, 0)
                    assert io.input_char() == ord("Q")
    assert three_input_corpus_size("Monotonic Boolfuck") == 36526
