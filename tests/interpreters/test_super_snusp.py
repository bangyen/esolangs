"""Execution tests for Super SNUSP and its boolean generator."""

from itertools import product

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.super_snusp import _advance, run
from esolangs.interpreters.io import IO
from esolangs.tools.super_snusp import super_snusp
from tests.interpreters.runner import run_program


def run_super(program: str, stdin: str = "") -> str:
    """Run a grid program and return its captured output."""
    return run_program(run, program.splitlines(), stdin)


def test_character_and_decimal_loads_mix_in_one_program() -> None:
    """Letters load as ``H.``, other bytes as decimal literals, in one run."""
    program = '"H.e.l..o.44.32.W.o.r.l.d.33.10.0.255.'
    assert run_super(program) == "Hello, World!\n\x00\xff"


def _run_boolean(program: str, bits: tuple[int, ...]) -> str:
    stdin = "".join(f"{bit}" for bit in bits)
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


@pytest.mark.medium
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


def test_empty_program_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        run([""], IO())


def test_advance_short_circuits_once_the_cursor_has_left_the_grid() -> None:
    """A done state is its own successor, so the shell can stop on it."""
    done = ((0, 0, 0), (0, ()), (), False, True)
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
    state = ((0, 0, 0), (0, ((0, 5),)), (1,), False, False)
    with pytest.raises(HaltError):
        _advance(state, [command], random_offset=offset)
