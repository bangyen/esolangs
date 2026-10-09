"""packlang generator tests."""

import random

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs._evaluate import _evaluate
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.packlang import run as packlang_run
from esolangs.tools.wrap import balance_score, wrap_program


class TestPacklangPaintedArray:
    """Fast structural coverage for Packlang's painted array."""

    def test_a_constant_table_paints_per_block_not_per_row(self) -> None:
        """Both fold routes: an all-zero block writes nothing, a full one fills."""
        assert "INCR t(" not in boolean.packlang("0000")
        assert "While q^7Do{" in boolean.packlang("11111110")
        assert "While q^127Do{" in boolean.packlang("1" * 127 + "0" * 129)
        # A painted row costs eleven characters, so two per row is well
        # under the cheapest per-row program either constant could have.
        biggest = max(len(boolean.packlang(bit * 1024)) for bit in "01")
        assert biggest < 2 * 1024, "a constant table is paying per row"

    def test_the_per_row_cost_does_not_grow_with_the_table(self) -> None:
        """Doubling a random table doubles what the rows cost, no more.

        Parity repeats its 128-row blocks, which are aliased and cost nothing.
        """
        rng = random.Random(0)
        sizes = []
        for n in (9, 10, 11):
            table = "".join(rng.choice("01") for _ in range(1 << n))
            sizes.append(len(boolean.packlang(table)))
        first, second = sizes[1] - sizes[0], sizes[2] - sizes[1]
        assert 1.8 < second / first < 2.2, sizes

    def test_a_run_of_ones_is_a_loop_and_a_lone_one_a_write(self) -> None:
        """Runs of ones loop; a lone one stays a single write."""
        table = "1" + "0" * 20 + "1" * 30 + "0" * 77
        program = boolean.packlang(table)
        assert "While q^51Do{INCR t(q);INCR q;}" in program
        assert "INCR t(0);" in program
        assert _evaluate("Packlang", program, inputs=7) == table

    @staticmethod
    def _blocks() -> list[str]:
        rng = random.Random(1)
        return ["".join(rng.choice("01") for _ in range(128)) for _ in range(4)]

    def test_a_repeated_block_is_aliased_to_its_first_copy(self) -> None:
        """Equal 128-row blocks cost less than distinct ones.

        ``f * 2`` would not do: it ignores its first input and is one block.
        """
        f, g, h, k = self._blocks()
        assert len(boolean.packlang(f + g + f + h)) < len(
            boolean.packlang(f + g + k + h)
        )

    @pytest.mark.medium
    def test_an_aliased_block_runs(self) -> None:
        f, g, h, _ = self._blocks()
        same = f + g + f + h
        assert _evaluate("Packlang", boolean.packlang(same), inputs=9) == same

    def test_an_alias_dearer_than_the_writes_is_not_taken(self) -> None:
        """A one-write block three blocks on repeats by writing again."""
        block = "0" * 127 + "1"
        zero = "0" * 128
        table = block + zero + zero + block
        assert boolean.packlang(table).count("INCR t(") == 2

    def test_repeats_shorter_than_a_block_are_aliased_and_run(self) -> None:
        """Eight 16-row tiles of two blocks: a smaller block aliases them."""
        rng = random.Random(2)
        a, b = ("".join(rng.choice("01") for _ in range(16)) for _ in range(2))
        tiled = (a + b) * 4
        program = boolean.packlang(tiled)
        assert "Array(Char,128)" not in program
        assert _evaluate("Packlang", program, inputs=7) == tiled


@pytest.mark.parametrize("indent", [0, 4, 16, 64])
def test_packlang_reduced_indent_crossing(indent):
    from esolangs.tools.packlang import _balance_form

    for table in ("0110", "0001", "10010110"):
        default = esolangs.generate("Packlang", table)
        program = "\n".join(
            " " * indent + row.lstrip() if row else row for row in default.split("\n")
        )
        widest = max(map(len, program.split("\n")))
        balanced = _balance_form(program, 1, widest)
        layouts = [
            wrap_program(program, "packlang", width) for width in range(1, widest + 1)
        ]
        assert balanced in layouts
        assert balance_score(balanced) == min(map(balance_score, layouts))
        assert (
            _evaluate("Packlang", balanced, inputs=len(table).bit_length() - 1) == table
        )


@pytest.mark.medium
@pytest.mark.parametrize(
    ("table", "width"),
    [("0110", 32), ("00110110011010100101110010100110", 32)]
    + [("00110110" * (2**n // 8), None) for n in (8, 11)],
)
def test_binary_digits_generated(table, width):
    source = boolean.packlang(table, width, literal_policy="binary_digits")
    n = (len(table) - 1).bit_length()
    for row in sorted({0, 1, 127 % len(table), len(table) // 2, len(table) - 1}):
        io = ScriptedIO(format(row, f"0{n}b"))
        packlang_run(source, io, literal_policy="binary_digits")
        assert io.getvalue() == table[row]


def test_literal_policy_is_checked_and_does_not_leak():
    with pytest.raises(ValueError, match="literal_policy"):
        boolean.packlang("01", literal_policy="binary")
    before = boolean.packlang("0110")
    boolean.packlang("0110", literal_policy="binary_digits")
    assert boolean.packlang("0110") == before
