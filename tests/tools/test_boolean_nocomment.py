"""Covers :mod:`esolangs.tools.nocomment`."""

import io
from collections.abc import Iterable
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO


class TestParameterizedNoComment:
    """Input-by-substitution boolean generator for the no-input language NoComment."""

    def run_nocomment(self, prog: str, tape: int | None = None) -> str:
        from esolangs.interpreters.tape_based.nocomment import _TAPE, run

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(prog, IO(), _TAPE if tape is None else tape)
        return buffer.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill through the shipped filler, not a copy of it.

        The setter here is one character and the same at every position, so
        a copy of it looks harmless -- but the generator counts instantiated
        positions when it lays out the template, so a copy that drifted in
        *width* would move every offset after it.  Minsky Swap's copy did
        exactly that and the suite hung rather than failing, which is a
        worse outcome than any this duplication was buying.
        """
        from esolangs.tools.examples import _fill_nocomment

        return _fill_nocomment(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools import parameterized

        template = parameterized.nocomment(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_nocomment(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.nocomment(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_nocomment(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools import parameterized

        template = parameterized.nocomment("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_program_structure(self) -> None:
        """A one-bit template computes the index then skips to the output."""
        from esolangs.tools import parameterized

        template = parameterized.nocomment("10")
        assert template.startswith("{X0}")
        assert "{C0}" not in template  # the complement is computed at runtime
        assert template.endswith("o")  # a single final output
        assert template.count("s") == 3  # NOT gate + guarded increment + index skip
        assert template.count("o") == 1

    def test_four_input_works(self) -> None:
        """A dense four-input table assembles and runs correctly."""
        from esolangs.tools import parameterized

        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            template = parameterized.nocomment("1010101010101010")
            got = self.run_nocomment(self.instantiate(template, bits))
            assert got == str(int("1010101010101010"[combo])), f"inputs {bits}"

    # The decode is exponential in the arity, so the swept cases cost
    # seconds: measured 9.3s at n=9 and 29.0s at n=10 (n=11 swept was 99.4s,
    # now sampled below).  n=9 used to stay in the fast run as the case
    # exercising the composed skip past a byte-sized index, but it is four
    # times the one-second budget every other case is held to.  The
    # mechanism is still proved on every push, just not at push time: CI's
    # `test` matrix job runs pytest unfiltered, so a slow-marked case runs
    # there like any other.  (The separate `-m slow` job is scoped to the
    # differential fuzzer's file and never selects these.)
    #
    # These are ~2x the figures first recorded here (4.1/13.0/43.5s), which
    # were measured before NoComment's tape became immutable.  The write
    # buffer that made that change affordable collapses *runs* of writes,
    # and this decode has none -- it writes a cell and moves -- so it pays a
    # tape rebuild on ~66% of steps.  Storing the tape as `bytes` rather
    # than a tuple of ints took the rebuild back to a memcpy and these cases
    # from 45.7/139.7/561.6s to what they are now; the residue over the
    # original is the immutable state the purity refactor bought.
    # n=11 is sampled rather than swept: the summand plan introduces no new
    # stage shape above n=10.  Measured plan sizes are q=2/4/6/10 at
    # n=8/9/10/11; n=9 first splits one bit's weight across stages, n=10
    # first carries both a repeated full stage and a mixed-cell stage, and
    # n=11 only repeats those same two shapes more often.  The emitter is a
    # uniform loop over plan entries with no branch keyed on stage index or
    # cell, so every shape is already swept exhaustively at the smallest
    # arity where it appears.  Sweeping n=11 cost 99.4s to re-prove that.
    @pytest.mark.parametrize(
        "n",
        [
            pytest.param(9, marks=pytest.mark.slow),
            pytest.param(10, marks=pytest.mark.slow),
        ],
    )
    def test_wide_arity_is_exact(self, n: int) -> None:
        """Past a byte-sized index the composed-skip decode still computes the table.

        A single ``s`` cannot carry an index past 255, which is what caps
        the narrow path at eight inputs.  Composing skips lifts that, so
        these arities must be exactly right on *every* input, not merely
        renderable -- each table below is run through the interpreter for
        all ``2**n`` combinations.
        """
        self._check_wide_arity(n, range(2**n))

    @pytest.mark.slow  # ~3s: the same decode at n=11, sampled
    def test_the_widest_arity_is_exact_on_sampled_rows(self) -> None:
        """The n=11 decode is checked where a stage boundary can go wrong.

        The rows are chosen rather than swept: every single-bit index, the
        all-zero and all-one rows, and both sides of each byte boundary --
        which is where a composed skip hands off between stages -- plus a
        stride through the rest so no region goes unvisited.
        """
        n = 11
        rows = {0, 2**n - 1}
        rows.update(1 << i for i in range(n))
        for edge in (255, 511, 1023, 2047):
            rows.update({edge - 1, edge, edge + 1} & set(range(2**n)))
        rows.update(range(0, 2**n, 41))
        self._check_wide_arity(n, sorted(rows))

    def _check_wide_arity(self, n: int, rows: Iterable[int]) -> None:
        """Run the four probe tables at arity ``n`` over ``rows``."""
        from esolangs.tools import parameterized

        tables = {
            "alternating": "01" * (2 ** (n - 1)),
            "parity": "".join(str(bin(r).count("1") % 2) for r in range(2**n)),
            "constant": "0" * (2**n),
            "and": "0" * (2**n - 1) + "1",
        }
        rows = list(rows)
        for name, table in tables.items():
            template = parameterized.nocomment(table)
            for combo in rows:
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_nocomment(self.instantiate(template, bits))
                assert got == table[combo], f"{name} n={n} inputs {bits}"

    def test_narrow_path_needs_a_byte_sized_index(self) -> None:
        """The single-skip decode covers exactly the arities whose index fits a byte.

        Derived from the interpreter's cell range rather than pinned: the
        skip amount is peeked off the stack and everything there came from a
        byte-sized cell, so the widest single-skip index is 255.
        """
        from esolangs.tools.parameterized import (
            _NOCOMMENT_NARROW_MAX,
            _NOCOMMENT_SKIP_MAX,
        )

        assert 2**_NOCOMMENT_NARROW_MAX - 1 <= _NOCOMMENT_SKIP_MAX
        assert 2 ** (_NOCOMMENT_NARROW_MAX + 1) - 1 > _NOCOMMENT_SKIP_MAX

    def test_cap_is_the_tape_not_the_skip(self) -> None:
        """The remaining cap is the interpreter's tape, and it is derived.

        The refusal must name the tape, and the boundary must be wherever
        the layout stops fitting -- so the largest arity that builds is
        found by asking, not asserted as a literal, and the next one up
        must raise.
        """
        from esolangs.interpreters.tape_based.nocomment import _TAPE
        from esolangs.tools import parameterized
        from esolangs.tools.parameterized import _NOCOMMENT_NARROW_MAX

        widest = 0
        for n in range(1, 16):
            try:
                parameterized.nocomment("0" * (2**n))
            except ValueError:
                break
            widest = n

        # The cap is past the byte-sized-index bound the narrow path has,
        # which is the whole point of the composed-skip decode.
        assert widest > _NOCOMMENT_NARROW_MAX
        with pytest.raises(ValueError, match=str(_TAPE)) as caught:
            parameterized.nocomment("0" * (2 ** (widest + 1)))
        assert "tape" in str(caught.value)

    def test_a_bigger_tape_lifts_the_cap(self) -> None:
        """The cap is the tape size, so a bigger tape moves it -- and still computes.

        The arity the default refuses is built against a larger tape and run
        on an interpreter given that same size, which is what makes this a
        lifted bound rather than a longer program that nothing can execute.
        A spot-check of inputs, not the sweep: :meth:`test_wide_arity_is_exact`
        already runs every combination at the arities the default reaches, and
        ``2**12`` runs of a 51k-command program is far too slow for the suite.
        """
        from esolangs.interpreters.tape_based.nocomment import _TAPE
        from esolangs.tools import parameterized

        n, tape = 12, 16384
        table = "".join(str((r * r + r // 3) % 2) for r in range(2**n))

        with pytest.raises(ValueError, match=str(_TAPE)):
            parameterized.nocomment(table)

        template = parameterized.nocomment(table, tape=tape)
        for combo in (0, 1, 2**n - 1, 2**n - 2, 1234, 2731):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_nocomment(self.instantiate(template, bits), tape)
            assert got == table[combo], f"n={n} inputs {bits}"


def test_nocomment_wide_declines_when_the_plan_outgrows_the_skip() -> None:
    """Past fifteen inputs the summand plan leaves no room to widen.

    ``room`` is what is left of a byte-sized skip once the guarded
    contribution's move-add-return block is paid for, and it goes negative at
    ``n == 15`` -- the plan stays at its one-cell form rather than being
    re-planned wider.  The build then stops on the tape limit, which is the
    reachable end of this path: the cell it would need is past 4096.
    """
    from esolangs.tools import parameterized

    table = "0" * (2**15 - 1) + "1"
    with pytest.raises(ValueError, match="past the interpreter's 4096-cell tape"):
        parameterized._nocomment_wide(table, 15, parameterized._TAPE)  # noqa: SLF001
