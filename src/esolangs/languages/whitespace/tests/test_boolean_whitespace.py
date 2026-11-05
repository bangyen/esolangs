"""Tests for the Whitespace Boolean generator."""

from pathlib import Path

import pytest

import esolangs
from esolangs import run
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row
from tests.support.witness_tables import SMALL_TABLES as TABLES


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    if table == "00":
        _check_constants()
        _check_power_steps()
    assert_every_row("Whitespace", table)


def _check_constants() -> None:
    from esolangs.languages.whitespace.generator import _END
    from esolangs.languages.whitespace.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate(
                    "Whitespace", bit * (1 << n), **options
                ).source
                assert len(program) == 7 * n + 11 + int(bit)
                assert program.endswith(_END)
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Whitespace", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "\n7\n", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.workspace_snapshot())
                        steps += 1
                        assert steps <= 2 * n + 3
                    assert steps == 2 * n + 3
                    peak = max(peak, written.bits)
                    assert (
                        written.bits
                        <= 5 + (2 * n + 3).bit_length() + (2 * n).bit_length()
                    )
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    assert io.input_num() == 7
                assert peak == 5 + (2 * n + 3).bit_length() + (2 * n).bit_length()
    assert (
        sum(len(esolangs.generate("Whitespace", f"{v:08b}").source) for v in range(256))
        == 22640
    )


def _check_power_steps() -> None:
    from esolangs.languages.whitespace.generator import whitespace
    from esolangs.languages.whitespace.interpreter import _Machine
    from esolangs.languages.whitespace.proof_formulas import execution, workspace
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in (1, 2, 3, 5, 8):
        size = 1 << n
        tables = ["0" * (size - 1) + "1"]
        # Every single essential position covers ignored reads before/after it.
        tables += [
            "".join(str((row >> (n - 1 - i)) & 1) for row in range(size))
            for i in range(n)
        ]
        peak = 0
        for table in tables:
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Whitespace", table, **options).source
                assert program == whitespace(table)
                # Exact saved bytes execute; stripping command terminators is invalid.
                assert program.endswith("\n")
                for row in (0, size // 3, size - 1):
                    stdin = "\n".join(f"{row:0{n}b}") + "\n7\n"
                    io = ScriptedIO(stdin)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.workspace_snapshot())
                        steps += 1
                        assert steps <= execution(n, program)
                    peak = max(peak, written.bits)
                    assert written.bits <= workspace(n, program)
                    assert io.getvalue() == table[row]
                    assert io.reads == n
                    assert io.past_end == 0
                    assert io.input_num() == 7
        assert peak == workspace(n, "")
    from pathlib import Path

    saved = Path(__file__).parents[1] / "whitespace.txt"
    for source in (saved, saved.read_text()):
        assert run("Whitespace", source, stdin="0\n1\n").output == "0"


@pytest.mark.parametrize("table", ["01", "0101", "0011", "0000", "0110"])
def test_exact_saved_commands_preserve_the_final_line_feed(
    tmp_path: Path, table: str
) -> None:
    from esolangs.languages.whitespace.generator import whitespace

    source = whitespace(table)
    path = tmp_path / "program.ws"
    path.write_bytes(source.encode())
    assert_every_row("Whitespace", table, program=path)


def test_cli_exports_exact_command_bytes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from esolangs.languages.whitespace.generator import whitespace
    from tests.support.cli_support import call_main

    output = call_main(["generate", "Whitespace", "0110"], capsys)
    assert output == whitespace("0110")
    path = tmp_path / "generated.ws"
    path.write_bytes(output.encode())
    assert run("Whitespace", path, stdin="0\n1\n").output == "1"
