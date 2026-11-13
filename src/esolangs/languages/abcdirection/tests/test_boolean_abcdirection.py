"""Tests for the ABCDirection Boolean generator."""

import random

import pytest

import esolangs
from esolangs.generation.token_balance import rendered_side
from esolangs.generation.wrap import balance_score
from esolangs.languages.abcdirection.generator import _floor, _plan, abcdirection
from tests.support.evaluation import _evaluate
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_native_rows, three_input_corpus_size
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer(monkeypatch) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        program = esolangs.generate("ABCDirection", table).source
        from esolangs.languages.abcdirection.interpreter import run

        assert_native_rows("ABCDirection", table, program, run, sentinel="Q")

        if table == "0001":
            from esolangs.generation.helpers import essential_inputs, read_at
            from esolangs.languages.abcdirection import generator

            assert generator.essential_inputs is essential_inputs
            assert generator.read_at is read_at
            for query, damaged_query, expected in (
                ("essential_inputs", lambda _table, _n: [], "0000"),
                (
                    "read_at",
                    lambda table, used, n: read_at(table, used, n).translate(
                        str.maketrans("01", "10")
                    ),
                    "1110",
                ),
            ):
                with monkeypatch.context() as patch:
                    patch.setattr(generator, query, damaged_query)
                    for balance in (False, True):
                        damaged = esolangs.generate(
                            "ABCDirection", table, balance=balance
                        ).source
                        assert _evaluate("ABCDirection", damaged, inputs=2) == expected


def _swept_side(table: str) -> int:
    """The squarest side over every helix width and the flat layout: the oracle."""
    n = len(table).bit_length() - 1
    flat = abcdirection(table)
    widths = range(_floor(table, n), len(flat.split("\n")[0]))
    helix = (rendered_side(w, _plan(table, n, w).height) for w in widths)
    return min(balance_score(flat)[0], *helix)


def test_balance_is_near_the_swept_optimum() -> None:
    """Two named widths stay within 10% of the best of every width (sum)."""
    rng = random.Random(3)
    tables = [
        "".join(rng.choice("01") for _ in range(1 << n))
        for n in range(2, 9)
        for _ in range(8)
    ]
    got = swept = 0
    for table in tables:
        program = str(esolangs.generate("ABCDirection", table, balance=True).source)
        got += balance_score(program)[0]
        swept += _swept_side(table)
    assert swept <= got <= 1.1 * swept


def test_balance_of_the_constant_zero_n3_is_exact() -> None:
    """The helix's print units are priced at their real width: (side, length, width)."""
    program = str(esolangs.generate("ABCDirection", "00000000", balance=True).source)
    assert balance_score(program) == (34, 559, 34)


def test_balance_of_xor_n2_is_exact() -> None:
    """The tight width charges reads and band cells, not the write: 37x16."""
    program = str(esolangs.generate("ABCDirection", "0110", balance=True).source)
    assert balance_score(program) == (37, 607, 37)


def test_balance_of_a_four_input_table_is_exact() -> None:
    """The width model prices each print unit at five columns; pricing
    one at six widens the helix a full lap: (side, length, width)."""
    program = str(
        esolangs.generate("ABCDirection", "1010010010000110", balance=True).source
    )
    assert balance_score(program) == (45, 919, 45)


def test_balance_of_parity_n8_cuts_the_long_runs() -> None:
    """Runs over 2 * sqrt(T) split into gadgets; uncut, the 136-column first
    gadget held the side at 140: (side, length, width)."""
    table = "".join(str((row).bit_count() & 1) for row in range(256))
    program = str(esolangs.generate("ABCDirection", table, balance=True).source)
    assert balance_score(program) == (84, 3059, 84)


def test_balance_of_not_n1_is_exact() -> None:
    """The tight width's slack is four columns, for the lap's landing
    and drop; a fifth widens even the one-input helix: (34, 559, 34)."""
    program = str(esolangs.generate("ABCDirection", "01", balance=True).source)
    assert balance_score(program) == (34, 559, 34)


@pytest.mark.parametrize("n", [1, 3, 7, 8, 12])
@pytest.mark.parametrize("bit", ["0", "1"])
@pytest.mark.parametrize("balanced", [False, True])
def test_constant_teeth_consume_whole_bytes(n, bit, balanced) -> None:
    from esolangs.languages.abcdirection.interpreter import run

    program = esolangs.generate("ABCDirection", bit * (1 << n), balance=balanced).source
    if n == 8 and not balanced:
        assert len(program) == 559
    rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
    for row in rows:
        io = ReadFirstIO(format(row, f"0{n}b") + "Q", expected=n)
        run(program, io)
        assert io.getvalue() == bit
        assert io.reads == n
        assert io.input_char() == ord("Q")


def test_three_input_corpus_size() -> None:
    assert three_input_corpus_size("ABCDirection") == 133684
