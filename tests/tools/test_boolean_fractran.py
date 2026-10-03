"""fractran generator tests."""

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import run as run_fractran
from esolangs.tools.fractran import PAIR as FRACTRAN_PAIR
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.tools.reader_support import _bits


def _fractran_answer(table: str, row: int) -> str:
    """Return what the instantiated FRACTRAN program stopped on."""
    n = len(table).bit_length() - 1
    template = boolean.fractran(table)
    program = fill_runs(template, TEMPLATE_CHAR, [FRACTRAN_PAIR] * n, _bits(row, n))
    io = ScriptedIO("")
    run_fractran(program, io)
    return io.getvalue()


@pytest.mark.parametrize("table", ["1000000000000000"])
def test_fractran_answers_four_input_and(table: str) -> None:
    n = len(table).bit_length() - 1
    for row in range(2**n):
        answer = "2" if table[row] == "1" else "1"
        assert _fractran_answer(table, row) == answer, (table, row)


def test_fractran_spends_nothing_a_run_never_divides() -> None:
    """No ``p^1``, no clear a block's path spends, no phase on the parity.

    A block's path consumes every input and the offset, so the ``1/p``
    clears are for a folded leaf alone; and the parity fractions come after
    every phase prime's own exit, so they need no guard.  The 256
    three-input tables went from 50,700 characters to 41,010.  Five inputs,
    since a smaller table ships as the plain tree.
    """
    from esolangs.tools.fractran import _packed

    parity = str(boolean.fractran("0110100110010110" * 2))
    assert "^1 " not in parity
    assert "^1*" not in parity
    assert parity.endswith(" 1/3^2 2/3")  # no leaf folds, so nothing to clear
    tables = [format(i, "08b") for i in range(256)]
    assert sum(len(_packed(t, 3)) for t in tables) == 41_010


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
def test_fractran_ships_the_plain_tree_where_the_decoder_costs_more() -> None:
    """Small trees beat packed blocks in source size and executed steps."""
    from esolangs.tools.fractran import _packed, _plain

    tables = [format(i, "08b") for i in range(256)]
    size = steps = old_size = old_steps = 0
    for table in tables:
        template, packed = boolean.fractran(table), _packed(table, 3)
        assert template == _plain(table, 3), table
        cost, old_cost = _fractran_steps(template, 3), _fractran_steps(packed, 3)
        assert len(template) <= len(packed), table
        assert cost <= old_cost, table
        size, steps = size + len(template), steps + cost
        old_size, old_steps = old_size + len(packed), old_steps + old_cost
    assert (old_size, size) == (41_010, 27_842)
    assert (old_steps, steps) == (34_314, 9_592)


def test_fractran_runs_inside_the_block_it_reads() -> None:
    """A run is bounded by one block, never by the table.

    The tree spends a step a level and the decoder traverses a single block's
    exponent, so a run costs ``O(2**w)`` for a block of ``w`` entries -- and
    ``w = Theta(n)``, which makes the step count polylogarithmic in ``T``.
    That is what the packed text buys its characters with, and why
    ``_plan`` holds the width near ``n / 3``: this ceiling is the thing that
    would grow if it stopped.
    """
    from esolangs.interpreters.other.fractran import _Machine
    from esolangs.tools.fractran import _plan

    for n in range(2, 8):
        table = "".join(str((row * row + 1) % 2) for row in range(2**n))
        v, wide = _plan(n)
        widest = 1 << (v + 1 if wide else v)
        ceiling = 4 * (1 << widest) + 4 * n
        template = boolean.fractran(table)
        for row in range(2**n):
            program = fill_runs(
                template, TEMPLATE_CHAR, [FRACTRAN_PAIR] * n, _bits(row, n)
            )
            machine = _Machine(program, ScriptedIO(""))
            steps = 0
            while not machine.halted:
                machine.step()
                steps += 1
            assert steps <= ceiling, (n, row, steps, ceiling)


@pytest.mark.parametrize("width", [1, 4, 5, 8, 9, 80])
@pytest.mark.parametrize("as_string", [False, True])
def test_fractran_phase_parity_public_uniform_setters(
    width: int, *, as_string: bool
) -> None:
    from esolangs.tools.fractran import fractran_setters

    template = esolangs.generate("FRACTRAN", "0110", width)
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
        program = esolangs.generate("FRACTRAN", table, width)
        for row in [0, 1, 2**n // 3, 2**n - 1]:
            bits = list(map(int, format(row, f"0{n}b")))
            filled = esolangs.instantiate("FRACTRAN", program, bits)
            assert (
                esolangs.read_answer("FRACTRAN", esolangs.run("FRACTRAN", filled))
                == table[row]
            )
