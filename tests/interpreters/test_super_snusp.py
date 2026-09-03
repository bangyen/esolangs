"""Execution tests for Super SNUSP and its boolean generator."""

from itertools import product

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.super_snusp import run
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.randomness import FirstDraw
from esolangs.tools.boolean.super_snusp import super_snusp
from esolangs.tools.text.super_snusp import super_snusp as super_snusp_text
from tests.interpreters.runner import run_program


def run_super(program: str, stdin: str = "") -> str:
    """Run a grid program and return its captured output."""
    return run_program(run, program.splitlines(), stdin)


def test_start_marker_and_literal_emit() -> None:
    assert run_super('"65.') == "A"


def test_lurd_mirror_turns_rightward_flow_downward() -> None:
    assert run_super('"65\\\n   .') == "A"


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        ('"?65.', chr(5)),  # zero skips the 6 and emits the literal 5.
        ('"1?65.', "A"),  # nonzero falls through and builds 65.
        ('"1{2+.', chr(3)),  # ADD reads the stack top without consuming it.
        ('"5{1=.', chr(3)),  # RAND alone consumes its stack argument.
    ],
)
def test_core_linear_opcodes(program: str, expected: str) -> None:
    if "=" in program:
        io = ScriptedIO()
        run(program.splitlines(), io, rng=FirstDraw(2))
        assert io.getvalue() == expected
    else:
        assert run_super(program) == expected


def test_decimal_io_and_output() -> None:
    assert run_super('"@#', "-42\n") == "-42"


def test_text_generator_round_trips_bytes_and_uses_letter_opcodes() -> None:
    text = "Hello, World!\n\x00\xff"
    program = super_snusp_text(text)
    assert run_super(program) == text
    assert "H." in program


def test_text_generator_accepts_empty_text_and_rejects_non_bytes() -> None:
    assert run_super(super_snusp_text("")) == ""
    with pytest.raises(ValueError, match="bytes"):
        super_snusp_text("\u0100")


@pytest.mark.parametrize("program", ['"+', '"0{1:', '"1_{1['])
def test_invalid_stack_and_arithmetic_operations_raise_halt_error(program: str) -> None:
    with pytest.raises(HaltError):
        run(program.splitlines(), IO())


def _run_boolean(program: str, bits: tuple[int, ...]) -> str:
    stdin = "".join(f"{bit}\n" for bit in bits)
    return run_super(program, stdin)


def test_every_two_input_table_executes_without_rand() -> None:
    for value in range(16):
        table = format(value, "04b")
        program = super_snusp(table)
        assert program.startswith('"')
        assert "=" not in program
        for bits in product((0, 1), repeat=2):
            row = bits[0] * 2 + bits[1]
            assert _run_boolean(program, bits) == table[row], (table, bits, program)


def test_three_input_generator_executes_every_table() -> None:
    for value in range(256):
        table = format(value, "08b")
        program = super_snusp(table)
        assert "=" not in program
        for bits in product((0, 1), repeat=3):
            row = bits[0] * 4 + bits[1] * 2 + bits[2]
            assert _run_boolean(program, bits) == table[row], (table, bits, program)


@pytest.mark.parametrize(
    "table",
    ["0000000000000001", "0110100110010110", "1111111111111111"],
)
def test_four_input_generator_executes(table: str) -> None:
    program = super_snusp(table)
    for bits in product((0, 1), repeat=4):
        row = sum(bit << (3 - index) for index, bit in enumerate(bits))
        assert _run_boolean(program, bits) == table[row], (table, bits, program)


def test_generator_rejects_invalid_table() -> None:
    with pytest.raises(ValueError, match="power-of-two"):
        super_snusp("011")
