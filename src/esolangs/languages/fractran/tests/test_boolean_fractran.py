"""fractran generator tests."""

from collections.abc import Iterator

import pytest

import esolangs
from esolangs import run
from esolangs._bindings import TEMPLATE_CHAR, fill_runs, runs
from esolangs.generation.wrap import balance_program, balance_score
from esolangs.languages.fractran import generator as boolean
from esolangs.languages.fractran.descriptor import PAIR as FRACTRAN_PAIR
from esolangs.languages.fractran.generator import fractran
from esolangs.languages.fractran.interpreter import _Machine
from esolangs.languages.fractran.interpreter import run as run_fractran
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace, make_vm
from scripts.benchmark import WrittenState
from tests.generators.reader_support import _TABLES
from tests.support.analysis_support import assert_analysis_complement
from tests.support.evaluation import _evaluate
from tests.support.generator_support import constant_artifacts, evaluate_generated
from tests.support.witness_tables import row_bits as _bits
from tests.support.witness_tables import witnesses


def _fractran_answers(table: str) -> Iterator[str]:
    """Run each filled row of one template with fresh interpreter state."""
    n = len(table).bit_length() - 1
    template = boolean.fractran(table)
    for row in range(1 << n):
        program = fill_runs(template, TEMPLATE_CHAR, [FRACTRAN_PAIR] * n, _bits(row, n))
        io = ScriptedIO("")
        run_fractran(program, io)
        yield io.getvalue()


@pytest.mark.parametrize("table", _TABLES)
def test_fractran_answers_every_row(table: str) -> None:
    for bit, actual in zip(table, _fractran_answers(table), strict=True):
        assert actual == ("2" if bit == "1" else "1"), table


@pytest.mark.slow
def test_fractran_answers_every_table_to_three_inputs() -> None:
    """Together with the fast corpus, exhaust every table and row through n=3."""
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = f"{value:0{2**n}b}"
            if table in _TABLES:
                continue
            for bit, actual in zip(table, _fractran_answers(table), strict=True):
                assert actual == ("2" if bit == "1" else "1"), table


def test_fractran_shares_equal_subtables() -> None:
    """No ``p^1``; parity at five inputs needs only 2n - 1 nodes, not 2**n - 1."""
    assert_analysis_complement("FRACTRAN", "reduced_diagram")
    parity = str(boolean.fractran("".join(str(r.bit_count() & 1) for r in range(32))))
    assert "^1 " not in parity
    assert "^1*" not in parity
    # A root, two nodes a level below it: two fractions a node.
    assert len(parity.split()) - 1 == 2 * (2 * 5 - 1)
    tables = [format(i, "08b") for i in range(256)]
    assert sum(len(boolean.fractran(t)) for t in tables) == 15_524


def _fractran_steps(template: str, n: int) -> int:
    """Return the steps every row of ``template`` runs to its halt, summed."""
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
    _check_native_constants()
    tables = [format(i, "08b") for i in range(256)]
    assert sum(_fractran_steps(boolean.fractran(t), 3) for t in tables) == 7_360
    for n in range(1, 8):
        table = "".join(str((row * row + 1) % 3 & 1) for row in range(2**n))
        # The machine's count includes the step that finds it halted.
        assert _fractran_steps(boolean.fractran(table), n) <= (n + 1) << n
        # One clear per set input, then the halt: 1 + popcount per row.
        constant = _fractran_steps(boolean.fractran("1" * 2**n), n)
        assert constant == 2**n + n * 2 ** (n - 1)


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


def test_fractran_parity_two_executes_at_every_width() -> None:
    for width in (1, 4, 8, 9, 80):
        for restored in (False, True):
            template = esolangs.generate("FRACTRAN", "0110", width=width)
            if restored:
                template = esolangs.from_json(
                    "FRACTRAN", esolangs.to_json("FRACTRAN", template)
                )
            for row, expected in enumerate("0110"):
                program = esolangs.instantiate(
                    "FRACTRAN", template, [row // 2, row % 2], truth_table="0110"
                )
                assert (
                    esolangs.read_answer("FRACTRAN", run("FRACTRAN", program).output)
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
                esolangs.read_answer("FRACTRAN", run("FRACTRAN", filled).output)
                == table[row]
            )


@pytest.mark.parametrize("program", ["", "1 22 333 4444"])
def test_nonuniform_cells_retain_tokens(program: str) -> None:
    balanced = balance_program(program, "fractran")
    assert balanced.split() == program.split()
    assert balance_score(balanced) <= balance_score(program)


def test_a_request_as_wide_as_the_widest_token_keeps_the_plain_root() -> None:
    """At width == the widest token the plain build stands; no swap is tried."""

    assert fractran("0001", 10) == "11*3^$*5^$\n2/35 1/7\n7/33 1/11\n1/5"


def test_balanced_width_bounds_stop_below_the_widest_token() -> None:
    """The balance regimes cap at the widest token minus one, not above it."""
    table = "0100110000110100000110010110110100111010011101100010000011011111"
    program = esolangs.generate("FRACTRAN", table, balance=True)
    rows = program.source.split("\n")
    assert (len(program.source), len(rows), max(map(len, rows))) == (431, 16, 30)
    assert _evaluate("FRACTRAN", program, inputs=6) == table


def test_fractran_parity_two_balances_and_executes() -> None:
    template = esolangs.generate("FRACTRAN", "0110", width=4)
    balanced = esolangs.generate("FRACTRAN", "0110", balance=True)
    assert _evaluate("FRACTRAN", template, inputs=2) == "0110"
    assert _evaluate("FRACTRAN", balanced, inputs=2) == "0110"


def _check_native_constants() -> None:
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("FRACTRAN")["workspace"].formula

    for n, bit, _options, template in constant_artifacts("FRACTRAN", range(1, 13)):
        assert len(runs(template.source, TEMPLATE_CHAR, [FRACTRAN_PAIR] * n)) == n
        assert len(template.source.split()) == n + 1
        peak = 0
        sizes = set()
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            bits = list(map(int, f"{row:0{n}b}"))
            program = esolangs.instantiate("FRACTRAN", template, bits)
            sizes.add(len(program.source))
            machine = make_vm("FRACTRAN", program)
            written = WrittenState(_capture_workspace(machine))
            steps = 0
            while not machine.halted:
                machine.step()
                written.sample(_capture_workspace(machine))
                steps += 1
                assert steps <= n + 1
            assert steps == 1 + sum(bits)
            assert esolangs.read_answer("FRACTRAN", machine.output) == bit
            assert written.bits <= workspace(n, template.source)
            peak = max(peak, written.bits)
        assert len(sizes) == 1
        assert peak == workspace(n, template.source)
