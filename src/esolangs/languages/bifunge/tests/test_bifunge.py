"""Bifunge raw playfields, byte I/O and Boolean execution."""

import pytest

import esolangs
from esolangs.exceptions import ExecutionBudgetError
from esolangs.languages.bifunge._commands import Command
from esolangs.languages.bifunge.interpreter import _Machine, _parse, run
from esolangs.runtime.io import ScriptedIO
from tests.support.prepared_support import check_split_factory_rejections
from tests.support.witness_tables import SMALL_TABLES, row_bits, witnesses


def _rows(*commands: str) -> list[str]:
    """Lay out hexadecimal opcodes as one command row."""
    blocks = [f"{int(command, 16):04b}" for command in commands]
    return ["".join(cell[:2] for cell in blocks), "".join(cell[2:] for cell in blocks)]


def _check_raw_playfields() -> None:
    commands = _rows(*("7B" * 16), "F", "B", "D")
    code = [row.translate(str.maketrans("01", "BA")) for row in commands]
    io = ScriptedIO("\x81é")
    run(code, io)
    assert io.getvalue() == "\x81é"

    for opcode, output in (("1", "\0"), ("2", "ÿ"), ("4", "ÿ")):
        io = ScriptedIO()
        # Empty pop -> zero, NOT -> one, combine it with another empty pop.
        run(_rows(*(("8" + opcode + "B") * 8), "D"), io)
        assert io.getvalue() == output, opcode

    for source in ([], ["10"], ["1", "10"], ["é0", "01"]):
        with pytest.raises(ValueError, match="Bifunge"):
            run(source, ScriptedIO())
    with pytest.raises(ExecutionBudgetError):
        esolangs.run(
            "Bifunge",
            "\n".join(_rows("A", "D")),
            limits=esolangs.ExecutionLimits(max_steps=20),
        )


def test_bifunge_execution() -> None:
    _check_raw_playfields()
    for table in (*SMALL_TABLES, *witnesses(3), *witnesses(4), *witnesses(5)):
        n = len(table).bit_length() - 1
        program = esolangs.prepare("Bifunge", esolangs.generate("Bifunge", table))
        for row, answer in enumerate(table):
            stdin = esolangs.encode_inputs("Bifunge", row_bits(row, n))
            got = program.run(stdin=stdin)
            assert (got.output, got.input_reads) == (answer, n), (table, row)


def test_bifunge_reference_model() -> None:
    from .oracle_checks import check_raw_bifunge

    check_raw_bifunge()


@pytest.mark.parametrize("table", ["0101", "01100110", "1111"])
def test_leading_ignored_input_needs_no_empty_stack_pop(table: str) -> None:
    source = esolangs.generate("Bifunge", table).source
    grid = _parse(source.splitlines())
    n = len(table).bit_length() - 1
    for row, answer in enumerate(table):
        stdin = esolangs.encode_inputs("Bifunge", row_bits(row, n))
        io = ScriptedIO(stdin)
        machine = _Machine(grid, io)
        for _ in range(500):
            if machine.halted:
                break
            command = grid[machine.y][machine.x]
            if command in (Command.AND, Command.OR, Command.XOR):
                assert len(machine.stack) >= 2
            elif command in (
                Command.NOT,
                Command.HORIZONTAL,
                Command.VERTICAL,
                Command.OUTPUT,
            ):
                assert machine.stack
            machine.step()
        assert machine.halted
        assert (io.getvalue(), io.reads) == (answer, n)


def test_split_factory_rejects_raw_source_and_options():
    from esolangs.languages.bifunge.interpreter import prepare_machine

    check_split_factory_rejections(prepare_machine, ["@"])
