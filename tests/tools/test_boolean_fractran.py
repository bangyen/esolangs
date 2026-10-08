"""fractran generator tests."""

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import run as run_fractran
from esolangs.tools.fractran import PAIR as FRACTRAN_PAIR
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.generator_support import evaluate_generated
from tests.tools.reader_support import _TABLES, _bits
from tests.witness_tables import witnesses


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
    assert sum(len(boolean.fractran(t)) for t in tables) == 22_376


def _fractran_steps(template: str, n: int) -> int:
    """Return the steps every row of ``template`` runs to its halt, summed."""
    from esolangs.interpreters.other.fractran import _Machine

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
    assert sum(_fractran_steps(boolean.fractran(t), 3) for t in tables) == 9_592
    for n in range(1, 8):
        table = "".join(str((row * row + 1) % 3 & 1) for row in range(2**n))
        # The machine's count includes the step that finds it halted.
        assert _fractran_steps(boolean.fractran(table), n) <= (n + 2) << n
        # One leaf, a clear a set bit, the halt: 2 + popcount summed over rows.
        constant = _fractran_steps(boolean.fractran("1" * 2**n), n)
        assert constant == 2 * 2**n + n * 2 ** (n - 1)


def test_fractran_programs_are_indexed() -> None:
    """Every base is a prime the interpreter sieves, so no run scans the list."""
    from esolangs.interpreters.other.fractran.index import compile_index

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
def test_fractran_phase_parity_public_uniform_setters(
    width: int, *, as_string: bool
) -> None:
    from esolangs.tools.fractran import fractran_setters

    template = esolangs.generate("FRACTRAN", "0110", width=width)
    if as_string:
        template = str(template)
    pairs = fractran_setters(template, 2)
    assert len(set(pairs)) == 1
    for row, expected in enumerate("0110"):
        program = esolangs.instantiate(
            "FRACTRAN", template, [row // 2, row % 2], truth_table="0110"
        )
        assert (
            esolangs.read_answer("FRACTRAN", esolangs.run("FRACTRAN", program))
            == expected
        )
        if width < 9:
            assert max(map(len, program.splitlines())) <= max(width, 4)
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        esolangs.instantiate("FRACTRAN", template, [0, 1], truth_table="0001")


def test_fractran_phase_parity_exact_resolver_and_size() -> None:
    from esolangs.tools.fractran import fractran, fractran_setters

    template = fractran("0110", 1)
    assert len(template) == 14
    assert max(map(len, template.splitlines())) == 3
    assert fractran_setters(template, 2) == (("1", "2"),) * 2
    legacy = fractran("0110", 4)
    assert fractran_setters(legacy, 2) == (("1", "5"),) * 2
    assert fractran_setters(legacy.replace("1/25", "1/5"), 2) == (("0", "1"),) * 2


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
