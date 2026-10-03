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


class TestParameterizedNoComment:
    """Input-by-substitution boolean generator for the no-input language NoComment."""

    def run_nocomment(self, prog: str, tape: int | None = None) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.nocomment import _TAPE, _Machine, run
        from tests.interpreters.test_nocomment_semantics import Reference

        size = _TAPE if tape is None else tape
        expected = Reference(prog, size)
        assert "b" not in expected.code
        for _ in range(len(expected.code) + 1):
            if expected.halted:
                break
            previous = expected.ip
            expected.step()
            assert expected.ip > previous
        assert expected.halted
        actual = _Machine(prog, ScriptedIO("unused"), size)
        for _ in range(len(expected.code) + 1):
            if actual.halted:
                break
            previous = actual.ind
            actual.step()
            assert actual.ind > previous
        assert actual.halted
        assert actual.snapshot() == expected.snapshot()
        assert actual.io.getvalue() == expected.output
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(prog, IO(), size)
        assert buffer.getvalue() == expected.output
        return expected.output

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs import instantiate

        setters = iter("i" if bit else "c" for bit in bits)
        independent = "".join(
            next(setters) if char == TEMPLATE_CHAR else char for char in tpl
        )
        assert tpl.count(TEMPLATE_CHAR) == len(bits)
        actual = instantiate("NoComment", tpl, bits)
        assert actual == independent
        return actual

    @pytest.mark.parametrize("n", [1, 2, 3])
    @pytest.mark.medium
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs import tools as generators

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = generators.nocomment(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_nocomment(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

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
        """Past a byte-sized index the stack-chain decode still computes the table.

        A single ``s`` cannot carry an index past 255, which is what caps
        the narrow path at eight inputs.  Chaining skips off the stack lifts
        that, so these arities must be exactly right on *every* input, not
        merely renderable -- each table below is run through the
        interpreter for all ``2**n`` combinations.
        """
        self._check_wide_arity(n, range(2**n))

    @pytest.mark.slow  # ~1s: the same decode at n=11, sampled
    def test_the_widest_arity_is_exact_on_sampled_rows(self) -> None:
        """The n=11 decode is checked where a stage boundary can go wrong.

        The rows are chosen rather than swept: every single-bit index, the
        all-zero and all-one rows, and both sides of each full-stage
        boundary -- where one bit's last stage hands off to the next bit's
        first -- plus a stride through the rest so no region goes unvisited.
        """
        n = 11
        rows = {0, 2**n - 1}
        rows.update(1 << i for i in range(n))
        for edge in (32, 64, 256, 1024):
            rows.update({edge - 1, edge, edge + 1})
        rows.update(range(0, 2**n, 41))
        self._check_wide_arity(n, sorted(rows))

    def test_the_chain_needs_six_cells_at_any_arity(self) -> None:
        """The chain's tape is six cells at any arity, and it runs on one that size.

        This is what removed the cap: the rows are in the code and the
        index is on the stack, so nothing on the tape grows with ``n``.
        The n=13 table is one the tape-resident decode refused on the
        default tape, and it is executed here on a *six*-cell one.
        """
        from esolangs import tools as generators

        n = 13
        table = "".join(str((r * r + r // 3) % 2) for r in range(2**n))
        template = generators.nocomment(table)
        assert set(template) <= set("idclrnfsbo") | {TEMPLATE_CHAR}
        for combo in (0, 1, 2**n - 1, 2**n - 2, 1234, 2731, 4096, 6000):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_nocomment(self.instantiate(template, bits), 6)
            assert got == table[combo], f"n={n} inputs {bits}"

    def test_the_chain_takes_over_where_it_is_smaller(self) -> None:
        """The dispatch is the measured crossover: the chain from four inputs.

        Over every table the chain is never the larger program at four
        inputs and the narrow decode is the smaller one on 218 of 256 at
        three; the two dense tables here are the boundary's two sides, and
        the dispatch is checked to follow the constant rather than restate
        it.
        """
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
            forced_narrow = generators.nocomment(four)
            assert len(forced_narrow) > len(chain)
        finally:
            module._NOCOMMENT_CHAIN_MIN = 4  # noqa: SLF001
        for table, templates in (
            (three, (narrow, chained)),
            (four, (chain, forced_narrow)),
        ):
            n = (len(table) - 1).bit_length()
            for template in templates:
                for row, output in enumerate(table):
                    bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
                    assert (
                        self.run_nocomment(self.instantiate(template, bits)) == output
                    )

    def test_the_chain_drops_ignored_inputs(self) -> None:
        """A table that ignores inputs is the smaller table's chain, and still right.

        Every input keeps its setter, so the instantiated width is the same,
        but an ignored input pushes no stage and the rows are the reduced
        table's -- which is what keeps NoComment in the reducing class past
        the narrow decode.
        """
        from esolangs import tools as generators

        n = 6
        table = "".join(str((r >> 4) & 1 ^ (r & 1)) for r in range(2**n))
        template = generators.nocomment(table)
        assert template.count(TEMPLATE_CHAR) == n * len(PAIR[0])
        parity = "".join(str(bin(r).count("1") % 2) for r in range(2**n))
        assert len(template) < len(generators.nocomment(parity))
        assert template.count("fsf") == 4 + 2 + 1  # four rows, two stages, a pad
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_nocomment(self.instantiate(template, bits), 6)
            assert got == table[combo], f"inputs {bits}"

    def test_the_chain_is_linear_in_the_table(self) -> None:
        """Six commands per row and a stage per 32: the size doubles with the table."""
        from esolangs import tools as generators

        sizes = []
        for n in (9, 10, 11, 12):
            table = "01" * 2 ** (n - 1)
            template = generators.nocomment(table)
            sizes.append(len(template))
            for row in (0, 1, 2 ** (n - 1), 2**n - 2, 2**n - 1):
                bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
                assert (
                    self.run_nocomment(self.instantiate(template, bits)) == table[row]
                )
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
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_nocomment(self.instantiate(template, bits))
                assert got == table[combo], f"{name} n={n} inputs {bits}"
