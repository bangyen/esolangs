"""unlambda generator tests."""

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import _validate_truth_table
from esolangs.tools.unlambda import unlambda
from tests.support.generator_support import verify_generated
from tests.tools.plain_oracles import separated_tree_text
from tests.tools.reader_support import _read_answer, assert_emissions_grow_by_a_line
from tests.tools.sample_tables import five_input_sample


@pytest.mark.medium  # both builds of 456 tables: 0.95s alone
def test_unlambda_binds_repeated_subtrees_and_skips_equal_halves() -> None:
    """Share-taking nodes cut both totals and lengthen no table."""

    three = [format(value, "08b") for value in range(256)]
    assert boolean.unlambda("01101001") == (
        "``@`d`k``s``?0i`d`@`d`k``s``?0ii``?1i`d`@`d`k``s``?0i`d`.1v``?1i`d`.0v"
        "``?1i`d`@`d`k``s``?1ii``?0i`d`@`d`k``s``?0i`d`.1v``?1i`d`.0v"
        "`d`@`d`k``s``?0i`d`.0v``?1i`d`.1v"
    )
    for tables, before, after in (
        (three, 41074, 32522),
        (five_input_sample(), 144722, 100963),
    ):
        plain = [len(unlambda_plain(table)) for table in tables]
        shared = [len(boolean.unlambda(table)) for table in tables]
        assert (sum(plain), sum(shared)) == (before, after)
        assert all(s <= p for s, p in zip(shared, plain, strict=True))
    for table in five_input_sample()[::10]:
        for row in range(32):
            assert _read_answer("unlambda", table, row) == (table[row], 5)
    for n in (4, 6):
        for value in (0x6996, 0x1234ABCD5678EF01):
            table = format(value % 2**2**n, f"0{2**n}b")
            assert verify_generated("Unlambda", table), table


def test_folding_shortens_a_constant_table() -> None:
    """A table whose rows agree collapses below one that folds nothing."""
    assert len(unlambda("00000000")) < len(unlambda("01101001"))


def test_the_plain_tree_grows_by_a_line() -> None:
    """The shipped build folds and shares subtrees, so the plain tree is measured."""

    assert_emissions_grow_by_a_line(unlambda_plain)


def unlambda_plain(truth_table: str) -> str:
    """Return the unshared tree of forced promises, ``29T - 25`` at most."""
    from esolangs.tools.unlambda import _READ, _leaf

    n = _validate_truth_table(truth_table)
    return separated_tree_text(
        truth_table,
        lambda level, row: _leaf(n, level, truth_table[row]),
        head=_READ + "````k`?1i```?0i`d",
        between="v`d",
        close="v",
    )
