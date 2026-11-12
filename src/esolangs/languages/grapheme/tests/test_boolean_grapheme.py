"""grapheme generator tests."""

import importlib
from unittest.mock import patch

import pytest

import esolangs
from esolangs import run as execute
from esolangs.exceptions import InputExhaustedError
from esolangs.languages.grapheme import generator as boolean
from esolangs.languages.grapheme.dialect import GraphemeDialect
from esolangs.languages.grapheme.generator import (
    _grapheme_literal,
    _grapheme_push65,
    _grapheme_table,
)
from esolangs.languages.grapheme.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.evaluation import _evaluate
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_constant_output,
    constant_programs,
    evaluate_generated,
)
from tests.support.witness_tables import _one_minterm


class TestGrapheme:
    def test_there_is_no_branch_left(self) -> None:
        """Indexing a literal needs no skip: parity emits no ``U``/``V``/``X``."""
        _check_constants()
        _check_seed()
        parity = boolean.grapheme("01101001")
        assert set("UVX").isdisjoint(parity)
        assert set("UVX").isdisjoint(boolean.grapheme("0" * 8))

    def test_the_program_is_only_grapheme_commands(self) -> None:
        """Only int-mode digits and the commands used are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.grapheme(table)) <= set("ABCDEFGHIKLMPRSTWYZ"), table
        for mode in ("between_letters", "after_each_letter"):
            program = boolean.grapheme("01", integer_conversion=mode)
            for line in ("B", "", "0", "1"):
                io = ScriptedIO(line + "\n")
                run(program, io, integer_conversion=mode)
                assert io.getvalue() == "0"


class TestGraphemeTable:
    """The one literal holding the table, and the index that shifts it."""

    def test_padding_never_reaches_an_entry(self) -> None:
        """Every entry survives the lift that forces a leading decimal 1."""
        for n in range(1, 9):
            for table in (_one_minterm(n), "01" * (2 ** (n - 1))):
                packed = _grapheme_table(table)
                assert str(packed)[0] == "1"
                low = format(packed % (1 << len(table)), f"0{len(table)}b")
                assert low == table

    @pytest.mark.parametrize("n", [6, 7, 8, 9])
    @pytest.mark.medium
    def test_a_table_using_every_input_still_computes(self, n: int) -> None:
        """Six essential inputs reached slot 5, whose old key was ``FFF``."""
        table = _one_minterm(n)
        assert evaluate_generated("Grapheme", table, timeout=60) == table

    def test_parity_at_six_inputs_computes(self) -> None:
        """Parity is the table with nothing to fold, so every input is live."""
        table = "".join(str((row).bit_count() & 1) for row in range(64))
        assert evaluate_generated("Grapheme", table, timeout=60) == table

    def test_a_literal_past_the_int_str_cap_computes(self) -> None:
        """n=14's ~5,000-digit literal raised at CPython's 4,300-digit cap."""
        table = "".join(str(row.bit_count() & 1) for row in range(1 << 14))
        program = esolangs.generate("Grapheme", table).source
        for row in (0, 5461, len(table) - 1):
            bits = [(row >> (13 - i)) & 1 for i in range(14)]
            stdin = esolangs.encode_inputs("Grapheme", bits)
            got = execute("Grapheme", program, stdin=stdin, timeout=60).output
            assert esolangs.read_answer("Grapheme", got) == table[row], row

    def test_an_off_by_one_shift_returns_a_wrong_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The positive control: the index is load-bearing, not decoration."""
        packed = _grapheme_table
        module = importlib.import_module("esolangs.languages.grapheme.generator")
        monkeypatch.setattr(module, "_grapheme_table", lambda t: 2 * packed(t))
        table = _one_minterm(6)
        assert evaluate_generated("Grapheme", table, timeout=60) != table


@pytest.mark.parametrize("mode", ["between_letters", "after_each_letter"])
def test_generator_literals_are_exact(mode: str) -> None:
    from esolangs.generation.helpers import read_at
    from esolangs.languages.grapheme.generator import grapheme

    assert boolean.read_at is read_at
    with patch.object(
        boolean,
        "read_at",
        side_effect=lambda table, *args: read_at(
            table.translate(str.maketrans("01", "10")), *args
        ),
    ) as corrupted:
        artifact = esolangs.generate(
            "Grapheme",
            "0011",
            settings=esolangs.Language("Grapheme").settings(integer_conversion=mode),
        )
        assert _evaluate("Grapheme", artifact, inputs=2) == "1100"
        assert corrupted.called
    for n in range(1, 13):
        for bit in "01":
            program = grapheme(bit * (1 << n), integer_conversion=mode)
            io = ScriptedIO(esolangs.encode_inputs("Grapheme", [1] * n) + "7\n")
            run(program, io, integer_conversion=mode)
            assert io.getvalue() == bit
            assert io.reads == n
            assert io.input_char() == ord("7")
    dialect = GraphemeDialect(integer_conversion=mode)
    for value in (
        0,
        1,
        2,
        5,
        6,
        13,
        16,
        60,
        76,
        600,
        706,
        766,
        106,
        1006,
        1263460,
        5666666,
        9999996,
        6 * 10**1000,
    ):
        io = ScriptedIO("")
        run(_grapheme_literal(value, dialect) + "Y", io, integer_conversion=mode)
        assert io.getvalue() == str(value)
    io = ScriptedIO("")
    run(_grapheme_push65(dialect) + "Y", io, integer_conversion=mode)
    assert io.getvalue() == "65"


def _check_constants() -> None:
    import esolangs

    for n, bit, _options, program in constant_programs("Grapheme", range(1, 13)):
        assert isinstance(program, str)
        for row in ("0" * n, "1" * n):
            io = ReadFirstIO(
                esolangs.encode_inputs("Grapheme", [int(b) for b in row]) + "7\n",
                expected=n,
            )
            assert_constant_output(run, program, io, bit, n)
            assert io.input_char() == ord("7")


def _check_seed() -> None:
    """The first essential factor survives ignored reads and underfeeding."""
    from esolangs.languages.grapheme.generator import grapheme

    for mode in ("between_letters", "after_each_letter"):
        for table in ("00001111", "00110011", "01010101", "01101001"):
            code = grapheme(table, integer_conversion=mode)
            for row in range(8):
                bits = f"{row:03b}"
                io = ReadFirstIO(
                    "".join("A\n" if bit == "1" else "%\n" for bit in bits) + "Q\n",
                    expected=3,
                )
                run(code, io, integer_conversion=mode)
                assert io.getvalue() == table[row]
                assert io.past_end == 0
                assert io.input_str() == "Q"
            for prefix in ("", "A\n", "A\nB\n"):
                with pytest.raises(InputExhaustedError):
                    run(code, ScriptedIO(prefix), integer_conversion=mode)
