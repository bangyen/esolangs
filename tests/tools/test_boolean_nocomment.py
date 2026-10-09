"""Covers :mod:`esolangs.tools.nocomment`."""

import importlib
import io
from collections.abc import Iterable
from contextlib import redirect_stdout
from itertools import pairwise

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools.helpers import TEMPLATE_CHAR
from esolangs.tools.nocomment import PAIR
from tests.witness_tables import row_bits


class TestParameterizedNoComment:
    """Input-by-substitution boolean generator for the no-input language NoComment."""

    def run_nocomment(self, prog: str, tape: int | None = None) -> str:
        from esolangs.interpreters.tape_based.nocomment import _TAPE, run

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(prog, IO(), _TAPE if tape is None else tape)
        return buffer.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill through the shipped filler, not a copy of it."""
        from tests.tools.fills import fill

        _fill_nocomment = fill("NoComment")

        return _fill_nocomment(tpl, bits)

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs import tools as generators

        template = generators.nocomment("0110")
        assert "{X" not in template
        assert template.count(TEMPLATE_CHAR) == 2 * len(PAIR[0])

    def test_four_input_works(self) -> None:
        """A dense four-input table assembles and runs correctly."""
        from esolangs import tools as generators

        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            template = generators.nocomment("1010101010101010")
            got = self.run_nocomment(self.instantiate(template, bits))
            assert got == str(int("1010101010101010"[combo])), f"inputs {bits}"

    # The chain falls through six commands per row past the landing, so a
    # full sweep is Theta(4**n) commands: up to 2.4s at n=9 and 6.9s at n=10 (the
    # tape-resident decode this replaced took 9.3s and 29.0s).  n=9 still
    # exceeds the one-second budget every other case is held to, so both
    # are slow-marked: CI's `test` matrix job runs pytest unfiltered, so a
    # slow-marked case runs there like any other.  (The separate `-m slow`
    # job is scoped to the differential fuzzer's file and never selects
    # these.)  n=11 is sampled rather than swept: a bit's stages are a
    # uniform loop keyed on nothing but its weight, and n=10 already has a
    # bit pushing a full stage 16, 8, 4, 2 times and once, and a bit at
    # every partial stage from 16 rows down to one; n=11 only pushes the
    # full stage more often.
    @pytest.mark.parametrize(
        "n",
        [
            pytest.param(9, marks=pytest.mark.slow),
            pytest.param(10, marks=pytest.mark.slow),
        ],
    )
    def test_wide_arity_is_exact(self, n: int) -> None:
        """Past a byte-sized index the stack-chain decode still computes the table."""
        self._check_wide_arity(n, range(2**n))

    @pytest.mark.slow  # ~1s: the same decode at n=11, sampled
    def test_the_widest_arity_is_exact_on_sampled_rows(self) -> None:
        """The n=11 decode is checked where a stage boundary can go wrong."""
        n = 11
        rows = {0, 2**n - 1}
        rows.update(1 << i for i in range(n))
        for edge in (32, 64, 256, 1024):
            rows.update({edge - 1, edge, edge + 1})
        rows.update(range(0, 2**n, 41))
        self._check_wide_arity(n, sorted(rows))

    def test_the_chain_needs_six_cells_at_any_arity(self) -> None:
        """The chain's tape is six cells at any arity, and it runs on one that size."""
        from esolangs import tools as generators

        n = 13
        table = "".join(str((r * r + r // 3) % 2) for r in range(2**n))
        template = generators.nocomment(table)
        assert set(template) <= set("idclrnfsbo") | {TEMPLATE_CHAR}
        for combo in (0, 1, 2**n - 1, 2**n - 2, 1234, 2731, 4096, 6000):
            bits = row_bits(combo, n)
            got = self.run_nocomment(self.instantiate(template, bits), 6)
            assert got == table[combo], f"n={n} inputs {bits}"

    def test_the_chain_takes_over_where_it_is_smaller(self) -> None:
        """The dispatch is the measured crossover: the chain from four inputs."""
        from esolangs import tools as generators
        from esolangs.tools.nocomment import _NOCOMMENT_CHAIN_MIN, _nocomment_chain

        assert _NOCOMMENT_CHAIN_MIN == 4
        three, four = "01101001", "0110100110010110"
        narrow = generators.nocomment(three)
        chained = _nocomment_chain(three, 3)
        assert narrow != chained
        assert len(narrow) < len(chained)
        chain = generators.nocomment(four)
        assert chain == _nocomment_chain(four, 4)
        module = importlib.import_module("esolangs.tools.nocomment")
        module._NOCOMMENT_CHAIN_MIN = 99  # noqa: SLF001
        try:
            assert len(generators.nocomment(four)) > len(chain)
        finally:
            module._NOCOMMENT_CHAIN_MIN = 4  # noqa: SLF001

    def test_the_chain_drops_ignored_inputs(self) -> None:
        """A table that ignores inputs is the smaller table's chain, and still right."""
        from esolangs import tools as generators

        n = 6
        table = "".join(str((r >> 4) & 1 ^ (r & 1)) for r in range(2**n))
        template = generators.nocomment(table)
        assert template.count(TEMPLATE_CHAR) == n * len(PAIR[0])
        parity = "".join(str(bin(r).count("1") % 2) for r in range(2**n))
        assert len(template) < len(generators.nocomment(parity))
        assert template.count("fsf") == 4 + 2 + 1  # four rows, two stages, a pad
        for combo in range(2**n):
            bits = row_bits(combo, n)
            got = self.run_nocomment(self.instantiate(template, bits), 6)
            assert got == table[combo], f"inputs {bits}"

    def test_the_chain_is_linear_in_the_table(self) -> None:
        """Six commands per row and a stage per 32: the size doubles with the table."""
        from esolangs import tools as generators

        sizes = [
            len(generators.nocomment("01" * 2 ** (n - 1))) for n in (9, 10, 11, 12)
        ]
        for small, big in pairwise(sizes):
            assert big < 2 * small, sizes
        assert sizes[-1] < 8 * 2**12, sizes

    def _check_wide_arity(self, n: int, rows: Iterable[int]) -> None:
        """Run the four probe tables at arity ``n`` over ``rows``."""
        from esolangs import tools as generators

        tables = {
            "alternating": "01" * (2 ** (n - 1)),
            "parity": "".join(str(bin(r).count("1") % 2) for r in range(2**n)),
            "constant": "0" * (2**n),
            "and": "0" * (2**n - 1) + "1",
        }
        rows = list(rows)
        for name, table in tables.items():
            template = generators.nocomment(table)
            for combo in rows:
                bits = row_bits(combo, n)
                got = self.run_nocomment(self.instantiate(template, bits))
                assert got == table[combo], f"{name} n={n} inputs {bits}"


@pytest.mark.medium
@pytest.mark.parametrize("bit", "01")
def test_every_constant_row_within_written_state_bound(bit: str) -> None:
    from esolangs.tools.nocomment import _program
    from tests.generator_support import assert_shared_program

    language = "NoComment"
    table = bit * 256
    plain = _program(table, keep_constant_input=True)
    commands = 3 * 256 + 3 * 256 // 32 + 240 * 8 - 491

    def workspace(p):
        return 32768 + 256 // 4 + 30 + len(p).bit_length()

    assert_shared_program(language, table, plain, commands, workspace)


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 11])
@pytest.mark.parametrize("bit", "01")
def test_balancing_retains_legacy_constant_shape(n: int, bit: str) -> None:
    from esolangs.tools.nocomment import _program
    from tests.generator_support import assert_constant_balanced_shape

    table = bit * (1 << n)
    assert_constant_balanced_shape(
        "NoComment", "nocomment", table, _program(table, keep_constant_input=True)
    )
