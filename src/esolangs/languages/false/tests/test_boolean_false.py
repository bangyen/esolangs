"""false generator tests."""

import pytest

import esolangs
from esolangs.languages import generators as boolean
from esolangs.languages.false.generator import false
from tests.generators.plain_oracles import separated_tree_text
from tests.generators.reader_support import assert_emissions_grow_by_a_line
from tests.generators.sample_tables import five_input_sample
from tests.support.generator_support import verify_generated
from tests.support.witness_tables import witnesses


def test_false_tests_the_low_bit_and_splits_every_node() -> None:
    """``1&`` is the bit; a node over two constant halves splits like any other."""

    assert boolean.false("0110") == "^1&$[^1&$[0.]?0=[1.]?]?0=[^1&$[1.]?0=[0.]?]?"
    assert boolean.false("0001") == "^1&$[^1&$[1.]?0=[0.]?]?0=[^%0.]?"
    total = sum(len(false_plain(f"{value:08b}", 3)) for value in range(256))
    assert total == 18528


def test_false_stores_repeated_halves_and_skips_equal_ones() -> None:
    """The reduced diagram cuts both totals and lengthens no table."""

    three = [format(value, "08b") for value in range(256)]
    assert boolean.false("01101001") == (
        "[^1&$[1.]?0=[0.]?]a:[^1&$[0.]?0=[1.]?]b:^1&$[^1&$a;?0=b;?]?0=[^1&$b;?0=a;?]?"
    )
    assert boolean.false("0101010100110011") == (
        "^1&$[^%^1&$[^%1.]?0=[^%0.]?]?0=[^%^%^1&$[1.]?0=[0.]?]?"
    )
    for tables, arity, before, after in (
        (three, 3, 18528, 15362),
        (five_input_sample(), 5, 65784, 41470),
    ):
        plain = [len(false_plain(table, arity)) for table in tables]
        shared = [len(boolean.false(table)) for table in tables]
        assert (sum(plain), sum(shared)) == (before, after)
        assert all(s <= p for s, p in zip(shared, plain, strict=True))
    for n in (4, 6):
        for value in (0x6996, 0x1234ABCD5678EF01):
            table = format(value % 2**2**n, f"0{2**n}b")
            assert verify_generated("FALSE", table), table


@pytest.mark.medium
def test_false_runs_out_of_variables_and_writes_the_rest_inline() -> None:
    """Past 26 repeated halves the rest stay written out, and still run."""
    import random

    table = format(random.Random(0).getrandbits(512), "0512b")
    program = boolean.false(table)
    assert all(f"]{name}:" in program for name in "abcdefghijklmnopqrstuvwxyz")
    assert verify_generated("FALSE", table)


@pytest.mark.medium
def test_false_single_character_floor_executes_every_small_table() -> None:
    for n in range(1, 4):
        for table in witnesses(n):
            program = esolangs.generate("FALSE", table, width=1)
            assert max(map(len, program.splitlines())) == 1
            for row, expected in enumerate(table):
                stdin = format(row, f"0{n}b")
                assert (
                    esolangs.run("FALSE", program, stdin=stdin, max_steps=100_000)
                    == expected
                )


def test_folding_shortens_a_constant_table() -> None:
    """A table whose rows agree collapses below one that folds nothing."""
    assert len(false("00000000")) < len(false("01101001"))


def test_the_plain_tree_grows_by_a_line() -> None:
    """The shipped build folds and shares subtrees, so the plain tree is measured."""

    assert_emissions_grow_by_a_line(
        lambda table: false_plain(table, len(table).bit_length() - 1)
    )


def false_plain(truth_table: str, n: int) -> str:
    """Return the tree with every half written out where it is used."""
    from esolangs.languages.false.generator import _SKIP, _TEST_ONE

    return separated_tree_text(
        truth_table,
        lambda level, row: _SKIP * (n - level) + truth_table[row] + ".",
        head=_TEST_ONE,
        between="]?0=[",
        close="]?",
        one_first=True,
    )
