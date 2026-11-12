"""false generator tests."""

import random
from unittest.mock import patch

import pytest

import esolangs
from esolangs import run as execute
from esolangs.languages.false.generator import _shared, false
from esolangs.languages.false.interpreter import run
from esolangs.runtime.io import ScriptedIO
from scripts.docs.evidence import construction_boundaries
from tests.generators.plain_oracles import separated_tree_text
from tests.generators.reader_support import assert_emissions_grow_by_a_line
from tests.generators.sample_tables import five_input_sample
from tests.support.analysis_support import assert_analysis_complement
from tests.support.generator_support import (
    assert_constant_roots,
    assert_saved_rows,
    verify_generated,
)
from tests.support.witness_tables import witnesses


def test_false_tests_the_low_bit_and_splits_every_node() -> None:
    """``1&`` is the bit; a node over two constant halves splits like any other."""

    assert_analysis_complement("FALSE", "decision_layers", "00")
    assert_analysis_complement("FALSE", "read_at")
    assert _shared("0110", 2) == "^1&$[^1&$[0.]?0=[1.]?]?0=[^1&$[1.]?0=[0.]?]?"
    assert _shared("0001", 2) == "^1&$[^1&$[1.]?0=[0.]?]?0=[^%0.]?"
    total = sum(len(false_plain(f"{value:08b}", 3)) for value in range(256))
    assert total == 18528
    # The shipped build prices ``+b&`` (complementary halves) at five chars; a
    # mispriced option grew 126 of 403 sampled tables with no other test red.
    assert sum(len(false(f"{value:08b}")) for value in range(256)) == 7523


def test_false_stores_repeated_halves_and_skips_equal_ones() -> None:
    """The reduced diagram cuts both totals and lengthens no table."""

    _check_lookup_and_cached_formula()
    three = [format(value, "08b") for value in range(256)]
    assert _shared("01101001", 3) == (
        "[^1&$[1.]?0=[0.]?]a:[^1&$[0.]?0=[1.]?]b:^1&$[^1&$a;?0=b;?]?0=[^1&$b;?0=a;?]?"
    )
    assert _shared("0101010100110011", 4) == (
        "^1&$[^%^1&$[^%1.]?0=[^%0.]?]?0=[^%^%^1&$[1.]?0=[0.]?]?"
    )
    for tables, arity, before, after in (
        (three, 3, 18528, 15362),
        (five_input_sample(), 5, 65784, 41470),
    ):
        plain = [len(false_plain(table, arity)) for table in tables]
        shared = [len(_shared(table, arity)) for table in tables]
        assert (sum(plain), sum(shared)) == (before, after)
        assert all(s <= p for s, p in zip(shared, plain, strict=True))
    for n in (4, 6):
        for value in (0x6996, 0x1234ABCD5678EF01):
            table = format(value % 2**2**n, f"0{2**n}b")
            assert verify_generated("FALSE", table), table


@pytest.mark.medium
def test_false_runs_out_of_variables_and_writes_the_rest_inline(monkeypatch) -> None:
    """Past 26 repeated halves the rest stay written out, and still run."""
    table = format(random.Random(0).getrandbits(512), "0512b")
    program = _shared(table, 9)
    assert all(f"]{name}:" in program for name in "abcdefghijklmnopqrstuvwxyz")
    assert verify_generated("FALSE", table)

    # Simulate a high input position without constructing a 2**27-entry table.
    monkeypatch.setattr(
        "esolangs.languages.false.generator.essential_inputs", lambda *_: [26]
    )

    def reject_expression(*_args, **_kwargs):
        raise AssertionError("expression variable exceeds the alphabet")

    monkeypatch.setattr(
        "esolangs.languages.false.generator._expression", reject_expression
    )
    assert false(table) == program
    for row in (0, 1, 127, 255, 511):
        output = execute("FALSE", program, stdin=f"{row:09b}", max_steps=10000).output
        assert output == table[row]


@pytest.mark.medium
def test_false_single_character_floor_executes_every_small_table() -> None:
    for n in range(1, 4):
        for table in witnesses(n):
            program = esolangs.generate("FALSE", table, width=1).source
            assert max(map(len, program.splitlines())) == 1
            for row, expected in enumerate(table):
                stdin = format(row, f"0{n}b")
                assert (
                    execute("FALSE", program, stdin=stdin, max_steps=100_000).output
                    == expected
                )


def test_folding_shortens_a_constant_table() -> None:
    """A table whose rows agree collapses below one that folds nothing."""
    assert_constant_roots("FALSE", run)
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


def _check_lookup_and_cached_formula() -> None:
    from esolangs.languages.false import generator
    from esolangs.languages.false.descriptor import LANGUAGE
    from esolangs.languages.false.generator import (
        _balance,
        _expression,
        _ExpressionSearch,
        _lookup,
        _splits,
    )

    language = esolangs.Language("FALSE")
    observed = {}

    def splits(table, positions):
        choices = _splits(table, positions)
        observed.setdefault(len(table), set()).add(len(choices))
        return choices

    for witness in construction_boundaries(language.name)["split_search_row_cutoff"]:
        n, table = witness.arity, witness.table()
        observed.clear()
        with patch.object(generator, "_splits", side_effect=splits):
            artifact = language.generate(table)
        assert observed[len(table)] == {n if n == 9 else 1}
        assert_saved_rows(
            language, artifact, table, (0, 1, len(table) // 2, len(table) - 1)
        )

    assert tuple(_splits("0" * 512, tuple(range(9)))) == tuple(range(9))
    assert _splits("0" * 1024, tuple(range(10))) == (0,)
    cases = [
        (5, table) for table in ("1" + "0" * 31, "0" * 31 + "1", "1" * 32, "01" * 16)
    ]
    cases.append((6, "01" * 32))
    for n, table in cases:
        program = _lookup(table, n, list(range(n)))
        assert LANGUAGE.backend.wrap is not None
        for source in (
            program,
            _balance(table, program),
            LANGUAGE.backend.wrap(program, 1),
        ):
            for row, expected in enumerate(table):
                io = ScriptedIO(f"{row:0{n}b}7")
                run(source, io)
                assert io.getvalue() == expected
                assert io.reads == n
                assert io.past_end == 0
                assert io.input_char() == ord("7")
    for source, expected in (
        ("' .", "32"),
        ("'\n.", "10"),
        ("123456789.", "123456789"),
    ):
        for width in (1, 2, 7):
            io = ScriptedIO("")
            run(LANGUAGE.backend.wrap(source, width), io)
            assert io.getvalue() == expected
    table = "".join(str(int(row.bit_count() >= 3)) for row in range(128))
    program = _expression(table, 7, list(range(7)))
    assert ";!" in program
    assert ";!" not in _ExpressionSearch(dict(enumerate("abcdefg"))).text(
        table, tuple(range(7)), budget=0
    )
    uncached = _ExpressionSearch(dict(enumerate("abcdefghijklmnopqrstuvwxyz"))).text(
        table, tuple(range(7))
    )
    assert ";!" not in uncached
    uncached = "".join(f"^1&{letter}:" for letter in "abcdefg") + uncached + "1&."
    for source in (program, uncached):
        for row, expected in enumerate(table):
            io = ScriptedIO(f"{row:07b}")
            run(source, io)
            assert io.getvalue() == expected
            assert io.reads == 7
