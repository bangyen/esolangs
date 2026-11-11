"""unlambda generator tests."""

import pytest

import esolangs
from esolangs.generation.helpers import _validate_truth_table
from esolangs.languages.unlambda import generator as boolean
from esolangs.languages.unlambda.generator import _READ, _leaf, unlambda
from scripts.benchmark import WrittenState
from tests.generators.plain_oracles import separated_tree_text
from tests.generators.reader_support import (
    _read_answers,
    assert_emissions_grow_by_a_line,
)
from tests.generators.sample_tables import five_input_sample
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import constant_programs, verify_generated


@pytest.mark.medium  # both builds of 456 tables: 0.95s alone
def test_unlambda_binds_repeated_subtrees_and_skips_equal_halves() -> None:
    """Share-taking nodes cut both totals and lengthen no table."""

    assert_analysis_complement("Unlambda", "SubtreeDiagram")
    _check_constants(range(5, 13))
    three = [format(value, "08b") for value in range(256)]
    assert boolean.unlambda("01101001") == (
        "``@`d`k``s``?0i`d`@`d`k``s``?1ii``?0i`d`@`d`k`|``si`kv"
        "``?1i`d`@`d`k``s``?0ii``?1i`d`@`d`k`|``si`kv"
        "`d`@`d`k``s``?0i``s.1e.0"
    )
    for tables, before, after in (
        (three, 41074, 28091),
        (five_input_sample(), 144722, 91017),
    ):
        plain = [len(unlambda_plain(table)) for table in tables]
        shared = [len(boolean.unlambda(table)) for table in tables]
        assert (sum(plain), sum(shared)) == (before, after)
        assert all(s <= p for s, p in zip(shared, plain, strict=True))
    for table in five_input_sample()[::10]:
        for expected, answer in zip(
            table, _read_answers("unlambda", table), strict=True
        ):
            assert answer == (expected, 5)
    for n in (4, 6):
        for value in (0x6996, 0x1234ABCD5678EF01):
            table = format(value % 2**2**n, f"0{2**n}b")
            assert verify_generated("Unlambda", table), table


def test_folding_shortens_a_constant_table() -> None:
    """A table whose rows agree collapses below one that folds nothing."""
    _check_constants(range(1, 5))
    assert len(unlambda("00000000")) < len(unlambda("01101001"))


def test_the_plain_tree_grows_by_a_line() -> None:
    """The shipped build folds and shares subtrees, so the plain tree is measured."""

    assert_emissions_grow_by_a_line(unlambda_plain)


def unlambda_plain(truth_table: str) -> str:
    """Return the unshared tree of forced promises, ``29T - 25`` at most."""
    n = _validate_truth_table(truth_table)
    return separated_tree_text(
        truth_table,
        lambda level, row: _leaf(n, level, truth_table[row]),
        head=_READ + "````k`?1i```?0i`d",
        between="v`d",
        close="v",
    )


def _check_constants(arities: range) -> None:
    from esolangs.languages.unlambda.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    _workspace = resource_bounds("Unlambda")["workspace"].formula

    for n, bit, options, program in constant_programs("Unlambda", arities):
        if not options:
            assert len(program) == 4 * n + 2
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs("Unlambda", list(map(int, f"{row:0{n}b}")))
            io = ReadFirstIO(stdin + "7", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, 999, written=written)
            assert io.getvalue() == bit
            assert io.past_end == 0
            assert io.input_char() == ord("7")
            if not options:
                assert steps == 14 * n + 2
                assert written.bits == _workspace(n, program)
