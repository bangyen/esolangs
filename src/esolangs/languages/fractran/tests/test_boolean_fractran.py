"""fractran generator tests."""

import pytest

import esolangs
from esolangs.generation.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.generation.wrap import balance_program, balance_score
from esolangs.languages import generators as boolean
from esolangs.languages.fractran.generator import PAIR as FRACTRAN_PAIR
from esolangs.languages.fractran.generator import fractran
from esolangs.languages.fractran.interpreter import run as run_fractran
from esolangs.runtime._evaluate import _evaluate
from esolangs.runtime.io import ScriptedIO
from tests.generators.reader_support import _TABLES
from tests.support.generator_support import evaluate_generated
from tests.support.witness_tables import row_bits as _bits
from tests.support.witness_tables import witnesses


def _fractran_answer(table: str, row: int) -> str:
    """Return what the instantiated FRACTRAN program stopped on."""
    n = len(table).bit_length() - 1
    template = boolean.fractran(table)
    program = fill_runs(template, TEMPLATE_CHAR, [FRACTRAN_PAIR] * n, _bits(row, n))
    io = ScriptedIO("")
    run_fractran(program, io)
    return io.getvalue()


@pytest.mark.parametrize("table", _TABLES)
def test_fractran_answers_every_row(table: str) -> None:
    n = len(table).bit_length() - 1
    for row in range(2**n):
        answer = "2" if table[row] == "1" else "1"
        assert _fractran_answer(table, row) == answer, (table, row)


@pytest.mark.slow
def test_fractran_answers_every_table_to_three_inputs() -> None:
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            for row in range(2**n):
                answer = "2" if table[row] == "1" else "1"
                assert _fractran_answer(table, row) == answer, (table, row)


def test_fractran_shares_equal_subtables() -> None:
    """No ``p^1``; parity at five inputs needs only 2n - 1 nodes, not 2**n - 1."""
    parity = str(boolean.fractran("".join(str(r.bit_count() & 1) for r in range(32))))
    assert "^1 " not in parity
    assert "^1*" not in parity
    # A root, two nodes a level below it, two leaves: two fractions a node.
    assert len(parity.split()) - 1 == 2 * (2 * 5 - 1) + 2
    tables = [format(i, "08b") for i in range(256)]
    assert sum(len(boolean.fractran(t)) for t in tables) == 19_678


def _fractran_steps(template: str, n: int) -> int:
    """Return the steps every row of ``template`` runs to its halt, summed."""
    from esolangs.languages.fractran.interpreter import _Machine

    steps = 0
    for row in range(2**n):
        program = fill_runs(template, TEMPLATE_CHAR, [FRACTRAN_PAIR] * n, _bits(row, n))
        machine = _Machine(program, ScriptedIO(""))
        while not machine.halted:
            machine.step()
            steps += 1
    return steps


@pytest.mark.medium
def test_fractran_runs_a_step_a_level() -> None:
    """A run fires at most n + 1 fractions; a constant table clears its set inputs."""
    tables = [format(i, "08b") for i in range(256)]
    assert sum(_fractran_steps(boolean.fractran(t), 3) for t in tables) == 9_408
    for n in range(1, 8):
        table = "".join(str((row * row + 1) % 3 & 1) for row in range(2**n))
        # The machine's count includes the step that finds it halted.
        assert _fractran_steps(boolean.fractran(table), n) <= (n + 2) << n
        # One leaf, a clear a set bit, the halt: 2 + popcount summed over rows.
        constant = _fractran_steps(boolean.fractran("1" * 2**n), n)
        assert constant == 2 * 2**n + n * 2 ** (n - 1)


def test_fractran_programs_are_indexed() -> None:
    """Every base is a prime the interpreter sieves, so no run scans the list."""
    from esolangs.languages.fractran.interpreter.index import compile_index

    for n in range(1, 11):
        table = "".join(str((row * 2654435761 >> 7) & 1) for row in range(2**n))
        program = fill_runs(
            boolean.fractran(table), TEMPLATE_CHAR, [FRACTRAN_PAIR] * n, [1] * n
        )
        assert compile_index(program) is not None, n


@pytest.mark.parametrize("width", [1, 4, 9, 40, 80])
def test_fractran_phase_parity_witness_tables(width: int) -> None:

    for n in range(1, 4):
        for table in witnesses(n):
            assert evaluate_generated("FRACTRAN", table, width=width) == table


@pytest.mark.parametrize("width", [1, 4, 8, 9, 80])
@pytest.mark.parametrize("as_string", [False, True])
def test_fractran_parity_two_executes_at_every_width(
    width: int, *, as_string: bool
) -> None:
    template = esolangs.generate("FRACTRAN", "0110", width=width)
    if as_string:
        template = str(template)
    for row, expected in enumerate("0110"):
        program = esolangs.instantiate(
            "FRACTRAN", template, [row // 2, row % 2], truth_table="0110"
        )
        assert (
            esolangs.read_answer("FRACTRAN", esolangs.run("FRACTRAN", program))
            == expected
        )
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        esolangs.instantiate("FRACTRAN", template, [0, 1], truth_table="0001")


@pytest.mark.parametrize("n", [4, 5, 6])
def test_fractran_phase_parity_retains_larger_layout_execution(n: int) -> None:

    table = "".join(str(row.bit_count() % 2) for row in range(2**n))
    for width in [1, 4, 80]:
        program = esolangs.generate("FRACTRAN", table, width=width)
        for row in [0, 1, 2**n // 3, 2**n - 1]:
            bits = list(map(int, format(row, f"0{n}b")))
            filled = esolangs.instantiate("FRACTRAN", program, bits)
            assert (
                esolangs.read_answer("FRACTRAN", esolangs.run("FRACTRAN", filled))
                == table[row]
            )


@pytest.mark.parametrize("program", ["", "1 22 333 4444"])
def test_nonuniform_cells_retain_tokens(program: str) -> None:
    balanced = balance_program(program, "fractran")
    assert balanced.split() == program.split()
    assert balance_score(balanced) <= balance_score(program)


def test_a_request_as_wide_as_the_widest_token_keeps_the_plain_root() -> None:
    """At width == the widest token the plain build stands; no swap is tried."""

    assert fractran("0001", 10) == "17*3^$*5^$\n1/7 2/11\n11/65 7/13\n13/51 7/17\n1/5"


def test_balanced_width_bounds_stop_below_the_widest_token() -> None:
    """The balance regimes cap at the widest token minus one, not above it."""
    table = "0100110000110100000110010110110100111010011101100010000011011111"
    program = str(esolangs.generate("FRACTRAN", table, balance=True))
    rows = program.split("\n")
    assert (len(program), len(rows), max(map(len, rows))) == (462, 16, 33)
    assert _evaluate("FRACTRAN", program, inputs=6) == table


def test_fractran_parity_two_balances_and_executes() -> None:
    from esolangs.languages.fractran.generator import _balance as _fractran

    balanced = _fractran("0110", esolangs.generate("FRACTRAN", "0110", width=4))
    assert _evaluate("FRACTRAN", balanced, inputs=2) == "0110"
