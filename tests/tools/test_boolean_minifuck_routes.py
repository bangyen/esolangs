"""Covers :mod:`esolangs.tools.minifuck` and :mod:`esolangs.tools.minifuck_mux`."""

import importlib
from unittest.mock import patch

import pytest

from esolangs.tools.helpers import essential_inputs
from tests.tools.minifuck_support import _MinifuckCase, _mux_separate, run_count


class TestParameterizedMinifuck(_MinifuckCase):
    """The generator end to end, and the routes before the lookup."""

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            # ``parameterized.minifuck`` searches, and it is the *build*
            # that costs, not the assertion: measured at one worker, a
            # two-input table takes 2.7s (NAND) to 9.0s (XOR) to emit while
            # a one-input table takes ~0.03s.  So the two-input cases carry
            # ``slow`` -- as does every other test in this class that builds
            # one -- and the one-input cases above stay in the fast run.
            pytest.param("0001", 2, marks=pytest.mark.slow),  # AND
            pytest.param("0110", 2, marks=pytest.mark.slow),  # XOR
            # XNOR and NAND -- unreachable in the reading model
            pytest.param("1001", 2, marks=pytest.mark.slow),
            pytest.param("1110", 2, marks=pytest.mark.slow),
            # OR ("0111") and NOR ("1000") are not listed: they cost ~48s and
            # ~47s here, and test_all_two_input_tables below already runs all
            # sixteen two-input tables through the same assertion.  The cases
            # that remain are the two one-input tables, which it does not
            # cover.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools import parameterized

        template = parameterized.minifuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_minifuck(self.instantiate(template, bits))
            assert got == table[combo], f"{table} inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        """Every two-input table builds, including the ones the wall named.

        A wall once recorded NAND, NOR and XNOR as unreachable.  It does not
        hold either way round: embedding lifts it, which is what this checks,
        and ``the relevant generator tests`` now also records a
        *reading* construction
        verifying all sixteen -- the searches behind the original claim were
        length-bounded well below what it needs.

        No longer marked ``slow``: the fixed mux rule builds all sixteen in
        milliseconds.
        """
        from esolangs.tools import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.minifuck(table)
            for combo in range(4):
                bits = [(combo >> (1 - i)) & 1 for i in range(2)]
                got = self.run_minifuck(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"

    @pytest.mark.slow  # builds all 38 degenerate three-input tables
    def test_degenerate_three_input_tables_never_search(self) -> None:
        """Every table with at most two essential inputs is search-free.

        A table that ignores an input is a smaller table wearing extra ones,
        so it projects onto a two-input problem -- which is a closed form.
        Nothing here needed its own construction; the arity below carries it.

        Ten of these come out with their slots *not* in ascending order, and
        all ten have the same shape: the ignored input is the *middle* one
        (essential ``[0, 2]``).  Emitting it first cannot sort them, since it
        already follows input 0, and no reset fixes it -- reconvergence
        works by driving every row to one state, so it cannot collapse
        ``x1`` while preserving ``x0``.  Searched to depth 14: none exists.
        Sorting those needs the solver to assign names.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        checked = 0
        # The searches these used to stub are gone; assert that structurally
        # instead of patching them, then build as before.
        assert not hasattr(module, "_find_column")
        assert not hasattr(module, "_find_parked")
        for table_int in range(256):
            table = format(table_int, "08b")
            if len(essential_inputs(table, 3)) > 2:
                continue
            checked += 1
            template = module.minifuck.__wrapped__(table)
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = self.run_minifuck(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"
        assert checked == 38, checked

    @pytest.mark.slow  # the four-input separation derivation, ~15s once
    def test_sculpted_route_computes_and_is_row_addressable(self) -> None:
        """``_mux`` builds a fully-essential table and every row is run.

        The sculpted route is what closes four inputs: a derived,
        table-independent suffix drives the sixteen rows to sixteen distinct
        pointer positions -- each input still embedded exactly once, the
        rule every generator here holds to -- and the printed column is then
        fixed one row at a time from the highest position down.  XOR4 is
        used because it is this file's historically pointed table.

        The separation claim is asserted structurally too: sixteen rows at
        sixteen distinct pointers, with each input's run appearing once,
        because row addressability without re-embedding is exactly what the
        route contributes.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        separated = _mux_separate(4)
        positions = separated.ptrs()
        assert len(set(positions)) == 16, positions
        assert run_count(separated.template(), 4) == 4

        table = "0110100110010110"
        template = module._mux(table, 4)  # noqa: SLF001
        assert template is not None
        assert run_count(template, 4) == 4
        widths = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    @pytest.mark.slow  # the six-input build, tens of seconds
    def test_no_arity_is_gated(self) -> None:
        """A fully-essential six-input table builds and prints all 64 rows.

        Six is the first arity the old ``_MUX_ARITIES = (2, 3, 4, 5)``
        declined, and it declined in **0.000s** -- a configuration gate, not
        a construction that failed.  ``the relevant generator tests``
        ("Is ``_mux`` total?") closes all six of the route's refusal sites
        with arguments carrying no
        residual ``n``, and the gate is now the floor
        :data:`_MUX_MIN_ARITY`, which only keeps constants and one-input
        projections on the :func:`_degenerate` path.

        This is the execution half of that claim, which is the half the repo's
        standing rule says a generated program is worth.  The table must be
        **fully essential**: a six-input table with a narrow core projects to
        an arity the old tuple already carried, so it built even while the
        gate stood, and asserting on one would test nothing.

        Every row is run and the widths compared, the same as at four inputs
        -- a template that computes the table but whose fills differ in length
        leaks its inputs through ``len(program)``.
        """

        from esolangs.tools.helpers import essential_inputs

        module = importlib.import_module("esolangs.tools.minifuck")
        assert module._MUX_MIN_ARITY == 2  # noqa: SLF001

        n = 6
        # Fixed table rather than a sampled one: a test that picks its own
        # table cannot fail reproducibly.
        table = "0110100110010110100101100110100101101001011010011100101101001010"
        assert len(table) == 2**n
        assert len(essential_inputs(table, n)) == n, "the table must be fully essential"

        template = module._solve(table)  # noqa: SLF001
        assert run_count(template, n) == n
        widths = set()
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    def test_sculpted_route_separates_every_arity_by_construction(self) -> None:
        """The separation is constructed, so it is exact and immediate.

        This used to pin the opposite: that five inputs declined, because no
        derivation had driven 32 rows to 32 distinct pointers and the
        searches took about three minutes to fail at it.  Weighting each
        input as it lands makes the pointer the row's binary expansion, so
        every arity separates in closed form -- and five is now built rather
        than declined.  What is pinned is the property the searches could
        not guarantee: ``2**n`` rows, ``2**n`` distinct pointers, fast.
        """
        import time

        for arity in (2, 3, 4, 5):
            start = time.monotonic()
            joint = _mux_separate(arity)
            assert joint is not None, arity
            assert len(set(joint.ptrs())) == 2**arity, arity
            assert time.monotonic() - start < 1.0, arity

    @pytest.mark.slow  # 3.1s: a five-input sculpted build plus all 32 rows
    def test_five_input_tables_build_and_print_every_row(self) -> None:
        """A five-input table builds through the sculpted route and runs.

        Five-input XOR is the pointed one: ``the relevant generator tests``
        records it as a table no search here builds at all.  Every row is
        run on the shipped interpreter, because a template that emits
        without computing would otherwise pass silently.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        table = "01101001100101101001011001101001"  # five-input XOR
        template = module._mux(table, 5)  # noqa: SLF001
        assert template is not None

        widths = set()
        for combo in range(32):
            bits = [(combo >> (4 - i)) & 1 for i in range(5)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    @pytest.mark.slow  # builds and runs all 256 three-input tables
    def test_every_three_input_table_is_search_free(self) -> None:
        """All 256 three-input tables build without searching.

        The searches this once stubbed are gone; every table builds by rule
        -- and every row is run, because a build that emits without
        computing would otherwise pass silently.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        searched = []
        # The searches these used to stub are gone; assert that structurally
        # instead of patching them, then build as before.
        assert not hasattr(module, "_find_column")
        assert not hasattr(module, "_find_parked")
        for table_int in range(256):
            table = format(table_int, "08b")
            try:
                template = module.minifuck.__wrapped__(table)
            except AssertionError:
                searched.append(table)
                continue
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = self.run_minifuck(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"
        assert searched == [], searched

    @pytest.mark.parametrize(
        ("table", "tier"),
        [
            ("0001", "scan"),  # AND: the embed's carry chain already holds it
            ("0110", "column search"),  # XOR: found by searching for a column
        ],
    )
    def test_the_search_tiers_still_build_when_the_cheap_routes_miss(
        self, table: str, tier: str
    ) -> None:
        """With the degenerate route stubbed off, ``_mux`` builds the table.

        Two-input tables are served by the degenerate route, so the mux is
        dead weight on the measured path there -- but it is the one total
        construction, and stubbing the cheap route is the only way to run it
        at this arity; well under a second, so this stays off the slow marker.

        The program is executed against every input row rather than merely
        being returned: a tier that builds the wrong thing is the failure
        this is here to catch.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        with patch.object(module, "_degenerate", lambda *_a, **_k: None):
            module.minifuck.cache_clear()
            try:
                template = module.minifuck.__wrapped__(table)
            finally:
                module.minifuck.cache_clear()

        assert template, f"the {tier} tier returned nothing"
        for combo in range(4):
            bits = [(combo >> 1) & 1, combo & 1]
            got = self.run_minifuck(self.instantiate(template, bits))
            assert got == table[combo], (tier, bits)

    def test_the_mux_uses_the_preloaded_strip_rule(self) -> None:
        """``_mux`` is exactly the named linear lookup construction."""

        module = importlib.import_module("esolangs.tools.minifuck")

        table = "1010000110011011"
        built = module._mux(table, 4)  # noqa: SLF001
        assert built is not None

        assert built == module._mux_lookup(table, 4)  # noqa: SLF001

    def test_template_is_input_independent_and_equal_length(self) -> None:
        """The template has placeholders and every fill has the same length.

        Both properties concern the same expensive ``0110`` construction.
        Building it separately only to inspect its runs duplicated
        construction without exercising a distinct path.  The current
        combined check takes 0.12s serially, so it belongs in the fast suite.
        """
        from esolangs.tools import parameterized

        template = parameterized.minifuck("0110")
        assert "{X" not in template
        assert run_count(template, 2) == 2
        lengths = {
            len(self.instantiate(template, [a, b])) for a in (0, 1) for b in (0, 1)
        }
        assert len(lengths) == 1, f"unequal instantiation lengths: {lengths}"

    def test_lift_appends_the_ignored_runs_or_refuses(self) -> None:
        """``_lift`` widens by appending runs, and refuses an order it cannot spell.

        The k-th run is input k, so an inner solve over inputs ``[0]`` lifts
        onto two inputs by one appended run; over ``[1]`` there is no
        renaming to fall back on, and the append would misname the runs.
        The refusal is what keeps ``_solve``'s fallback from ever emitting
        a template whose inputs are not the table's.
        """
        module = importlib.import_module("esolangs.tools.minifuck")
        inner = module._solve("01")  # noqa: SLF001

        lifted = module._lift(inner, [0], 2)  # noqa: SLF001
        assert lifted == inner + module._MINIFUCK_INPUT  # noqa: SLF001
        assert run_count(lifted, 2) == 2
        for a, b in ((0, 0), (0, 1), (1, 0), (1, 1)):
            assert self.run_minifuck(self.instantiate(lifted, [a, b])) == str(a)

        with pytest.raises(ValueError, match="misnames a run"):
            module._lift(inner, [1], 2)  # noqa: SLF001
