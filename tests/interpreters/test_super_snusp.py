"""Execution tests for Super SNUSP and its boolean generator."""

from itertools import product

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.super_snusp import _advance, run
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


def test_text_generator_round_trips_bytes_and_uses_shortest_load() -> None:
    text = "Hello, World!\n\x00\xff"
    program = super_snusp_text(text)
    assert run_super(program) == text
    assert "H." in program
    # A nearby non-letter byte is shorter as a signed delta than its decimal
    # literal: after a double quote (34), ! is one decrement and output.
    assert "34.(." in super_snusp_text('"!')


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


def test_generator_reduces_unused_inputs_but_reads_them() -> None:
    """Projection saves ANF work without leaving stream input behind."""
    reduced = super_snusp("00001111")  # depends only on the first input
    parity = super_snusp("01101001")
    assert reduced.count(",") == 3
    assert len(reduced) < len(parity)
    for bits in product((0, 1), repeat=3):
        assert _run_boolean(reduced, bits) == str(bits[0])


def test_generator_rejects_invalid_table() -> None:
    with pytest.raises(ValueError, match="power-of-two"):
        super_snusp("011")


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        ('"!965.', "A"),  # SKIP steps over the 9, leaving 65 to build.
        ("\"65.'99.", "A"),  # HALT ends the run before the second emit.
        ('"1{$65.', "A"),  # DROP discards the pushed 1 without reading it.
        ('"100{365%.', "A"),  # MOD: 365 % 100.
        ('"5{13*.', "A"),  # MUL reads the stack top.
        ('"5{325:.', "A"),  # DIV floors toward the operand.
        ('"2{4225;.', "A"),  # ROOT: the square root of 4225.
        ('"6{1[.', "@"),  # SHL by the stack top.
        ('"1{130].', "A"),  # SHR by the stack top.
        ('"66~_.', "C"),  # NOT gives -67; negating it emits 67.
        ('"66(.', "A"),  # DEC steps the cell down one.
        ('"64).', "A"),  # INC steps it up one.
        ('   .\n"65/', "A"),  # RULD mirror turns rightward flow upward.
    ],
)
def test_remaining_linear_opcodes(program: str, expected: str) -> None:
    assert run_super(program) == expected


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        ('"1_`65.\n', chr(5)),  # NEGSKIP steps over the 6 when the cell is < 0.
        ('"65_`.9.', "\t"),  # a negative cell skips the emit and builds 9.
    ],
)
def test_negative_skip_reads_the_cell_sign(program: str, expected: str) -> None:
    assert run_super(program) == expected


def test_char_input_writes_the_byte_it_read() -> None:
    assert run_super('",.', "A") == "A"


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        ('"100{365_%#', "-65"),  # MOD keeps the dividend's sign.
        ('"3{27_;#', "-3"),  # an exact odd root of a negative value.
        ('"3{9_;#', "-3"),  # an inexact one floors away from zero.
    ],
)
def test_negative_operands_keep_their_sign(program: str, expected: str) -> None:
    assert run_super(program) == expected


@pytest.mark.parametrize(
    "program",
    [
        '"0{1%.',  # MOD by zero.
        '"1_{1[.',  # SHL by a negative amount.
        '"1_{1].',  # SHR by a negative amount.
        '"0{4;.',  # ROOT of degree zero.
        '"2{65_;#',  # an even root of a negative value.
        '"1_.',  # chr() of a negative cell.
    ],
)
def test_invalid_operands_raise_halt_error(program: str) -> None:
    with pytest.raises(HaltError):
        run(program.splitlines(), IO())


def test_empty_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run([""], IO())


def test_advance_short_circuits_once_the_cursor_has_left_the_grid() -> None:
    """A done state is its own successor, so the shell can stop on it."""
    done = (0, 0, 0, 0, (), (), False, True)
    assert _advance(done, ['"']) == (done, None)


@pytest.mark.parametrize(
    ("command", "offset"),
    [
        (",", None),  # no byte was read.
        ("@", None),  # no number was read.
        ("=", None),  # no draw was made.
        ("=", 99),  # a draw outside the two operands' span.
    ],
)
def test_advance_refuses_an_input_the_shell_did_not_supply(
    command: str, offset: int | None
) -> None:
    """The shell always supplies these, so only a direct call reaches the guard.

    ``step`` reads a byte for ``,``, a number for ``@`` and a draw for ``=``
    before it calls the transition, and its own ``EOFError`` arrives first at
    a real end of input.  The guards are the pure function's contract with
    any other caller, and this is what holds them.
    """
    state = (0, 0, 0, 0, ((0, 5),), (1,), False, False)
    with pytest.raises(HaltError):
        _advance(state, [command], random_offset=offset)
