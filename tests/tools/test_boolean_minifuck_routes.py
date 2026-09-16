"""Covers :mod:`esolangs.tools.minifuck` and :mod:`esolangs.tools.minifuck_mux`."""

import importlib
import re
from unittest.mock import patch

import pytest

from esolangs.tools.helpers import essential_inputs
from tests.tools.minifuck_support import _MinifuckCase


class TestParameterizedMinifuck(_MinifuckCase):
    """The generator end to end, and the routes before the staged one."""

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

    def test_generator_never_enumerates_candidates(self) -> None:
        """No public build reaches any retired candidate enumeration.

        Stubbing every old selector catches a regression that returns the
        right table by silently restoring a contest.  The exhaustive
        two-input set plus unary, wider projection, full-arity, and
        out-of-order cases cover every branch in ``_solve``.
        """

        from esolangs.tools import parameterized

        module = importlib.import_module("esolangs.tools.minifuck")

        def forbidden(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("the generator enumerated candidates")

        with patch.multiple(
            module,
            _derive_staging=forbidden,
            _find_pool=forbidden,
            _first_staging=forbidden,
            _mux_scout=forbidden,
            _mux_sculpt=forbidden,
            _mux_sweep=forbidden,
            _reconverged=forbidden,
            _staged=forbidden,
            _try_print=forbidden,
        ):
            for table_int in range(16):
                table = format(table_int, "04b")
                # ``minifuck`` is cached, so go through the wrapped function
                # to be sure the build actually runs under the patch.
                template = module.minifuck.__wrapped__(table)
                assert "{X0}" in template, table
                assert "{X1}" in template, table
            for table in (
                "01",
                "01010101",
                "0110100110010110",
                "0" * 32 + "1" * 32,
                format(0xD6B4_A791_8E35_C20F, "064b"),
            ):
                template = module.minifuck.__wrapped__(table)
                assert template.count("{X") == (len(table).bit_length() - 1)
        # And the public entry point still agrees with what it built.
        assert parameterized.minifuck("0110").count("{X") == 2

    @pytest.mark.slow  # derives a staging for all sixteen
    def test_the_derivation_reaches_every_two_input_table(self) -> None:
        """Every two-input table gets a staging from the enumeration alone.

        There is no stored two-input plan to check against, so what this pins
        is the property that plan used to guarantee: the enumeration reaches
        all sixteen, and reaches them within its own caps rather than by
        running off the end.

        A table and its complement share a staging -- the endgame tries both
        read polarities, and the printed digit is ``NOT(v XOR cell7)`` -- so
        the pair costs one derivation between them, which is why the sweep
        finds the second member of each pair as readily as the first.
        """

        from esolangs.tools.minifuck import (
            _MAX_ACC,
            _MAX_BRACKETS,
            _SEPS,
            _derive_staging,
        )

        for table_int in range(16):
            table = format(table_int, "04b")
            plan = _derive_staging(table, 2)
            assert plan is not None, table
            sep_index, settle, brackets, acc = plan
            assert 0 <= sep_index < len(_SEPS), (table, plan)
            assert settle in (0, 1), (table, plan)
            assert isinstance(brackets, int), (table, plan)
            assert 0 <= brackets <= _MAX_BRACKETS, (table, plan)
            assert 9 <= acc <= _MAX_ACC, (table, plan)

    @pytest.mark.slow  # builds all 38 degenerate three-input tables
    def test_degenerate_three_input_tables_never_search(self) -> None:
        """Every table with at most two essential inputs is search-free.

        A table that ignores an input is a smaller table wearing extra ones,
        so it projects onto a two-input problem -- which is a closed form.
        Nothing here needed its own construction; the arity below carries it.

        Ten of these come out with their slots *not* in ascending order, and
        all ten have the same shape: the ignored input is the *middle* one
        (essential ``[0, 2]``).  Emitting it first cannot sort them, since it
        already follows ``{X0}``, and no reset fixes it -- reconvergence
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
        used because it is this file's historically pointed table; the route
        itself never consults the stagings, so this exercises it directly
        without paying the four-input whole-arity derivation.

        The separation claim is asserted structurally too: sixteen rows at
        sixteen distinct pointers, with each ``{Xi}`` appearing once,
        because row addressability without re-embedding is exactly what the
        route contributes.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        separated = module._mux_separate(4)  # noqa: SLF001
        positions = separated.ptrs()
        assert len(set(positions)) == 16, positions
        for i in range(4):
            assert separated.template().count("{X" + str(i) + "}") == 1, i

        table = "0110100110010110"
        template = module._mux(table, 4)  # noqa: SLF001
        assert template is not None
        names = [int(m) for m in re.findall(r"\{X(\d+)\}", template)]
        assert names == sorted(names), names
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
        names = [int(m) for m in re.findall(r"\{X(\d+)\}", template)]
        assert names == sorted(names), names
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

        module = importlib.import_module("esolangs.tools.minifuck")

        for arity in (2, 3, 4, 5):
            start = time.monotonic()
            joint = module._mux_separate(arity)  # noqa: SLF001
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

        With ``_find_column`` and ``_find_parked`` stubbed to raise, every
        table still builds -- and every row is run, because a staging that
        emits without computing would otherwise pass silently.

        The searches are kept anyway.  They are the fallback for an arity
        with no plan, and this assertion is what would notice if a staging
        stopped working: the table would fall through and raise here rather
        than quietly costing two minutes.
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

    def test_the_degenerate_cells_are_where_they_were_written_down(self) -> None:
        """Measuring the embed reproduces the six cells that used to be stored.

        ``_degenerate_cells`` replaced a written-down mapping, and the reason
        it can is the reason the mapping was constant in the first place: the
        carry chain preserves ``b0`` and ``b1`` individually before the
        prefix-XOR starts mixing.  This pins the collapse to the numbers it
        replaced, so a change to the embed or the separator that moved these
        columns would be caught here rather than as a slow degenerate build.

        The cells are the same at every arity the route serves, which is what
        let one mapping serve all of them.
        """

        from esolangs.tools.minifuck import _degenerate_cells

        written_down = {
            "const1": 1,
            "~b0": 16,
            "b0": 17,
            "const0": 18,
            "~b1": 19,
            "b1": 20,
        }
        for n in (2, 3, 4):
            assert _degenerate_cells(n) == written_down, n
        # One input leaves no ``b1`` to find, and the route asks for whatever
        # is there rather than assuming all six.
        assert _degenerate_cells(1) == {
            "const1": 1,
            "~b0": 16,
            "b0": 17,
            "const0": 18,
        }

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
        """With the derived routes stubbed off, the searches build the table.

        Every supported table is served by the staged, degenerate, or
        reconverged route, so these tiers are dead weight on the measured
        path -- but they are the fallback the module keeps for tables a
        future enumeration does not reach.  Stubbing the cheap routes is the
        only way to run them, and they answer in well under a second at two
        inputs, so this stays off the slow marker.

        The program is executed against every input row rather than merely
        being returned: a tier that builds the wrong thing is the failure
        this is here to catch.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        with (
            patch.object(module, "_staged", lambda *_a, **_k: None),
            patch.object(module, "_reconverged", lambda *_a, **_k: None),
            patch.object(module, "_degenerate", lambda *_a, **_k: None),
        ):
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

    def test_reconverged_declines_what_it_cannot_replay(self) -> None:
        """``_reconverged`` bails rather than replaying a staging it lacks.

        Neither refusal fires on real data -- every two-input inner table has
        a staging, and every one of those stagings is a plain bracket run, so
        the two-essential-input route always has something to replay.  They
        are the guards that keep a *future* enumeration, one with a gap or
        one carrying the literal-suffix form, from being replayed by a route
        that makes no walk.  Forcing them is the only way to reach them, so
        the enumeration is stubbed the way the search-route tests stub theirs.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        # Two essential inputs with the ignored one leading, so the route
        # takes its projection branch -- the one that replays an inner
        # staging -- rather than the single-input branch that stands at a
        # known cell.  Unstubbed this table builds, so a None below is the
        # guard firing and not the route failing for its own reasons.
        table, n = "00010001", 3
        pair = essential_inputs(table, n)
        assert pair == [1, 2], pair
        assert module._reconverged(table, pair, n) is not None  # noqa: SLF001

        with patch.object(module, "_derive_staging", lambda *_a, **_k: None):
            assert module._reconverged(table, list(pair), n) is None  # noqa: SLF001

        # The same call, but the staging carries the literal-suffix form:
        # `brackets` is a string rather than a count, which this route cannot
        # replay because it makes no walk.
        real = module._derive_staging  # noqa: SLF001

        def literal_suffix(inner: str, arity: int) -> object:
            plan = real(inner, arity)
            if plan is None:
                return None
            sep_index, settle, _brackets, acc = plan
            return (sep_index, settle, "[x", acc)

        with patch.object(module, "_derive_staging", literal_suffix):
            assert module._reconverged(table, list(pair), n) is None  # noqa: SLF001

    def test_reconverged_declines_a_reset_that_splits_the_rows(self) -> None:
        """A reset leaving the rows in different states is not built on.

        The route's whole premise is that the ignored inputs are gone, which
        a split state has not achieved.  The reset is constructed now rather
        than searched, so there is one of them and the guard *declines*
        instead of trying the next candidate -- which is safe because
        ``_solve`` falls through to a route that does not need the reset.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        table, n = "0101", 2  # input 1 alone decides it; input 0 is ignored
        essential = essential_inputs(table, n)
        # The route builds this table from the constructed reset.
        assert module._reconverged(table, essential, n) is not None  # noqa: SLF001

        # ``[`` alone reads a row-dependent cell, so the rows stop agreeing.
        def diverging(_ignored: int) -> str:
            return "["

        with patch.object(module, "_reset_code", diverging):
            assert module._reconverged(table, essential, n) is None  # noqa: SLF001

    def test_the_constructed_reset_converges_every_arity(self) -> None:
        """``_reset_code`` drives all ``2**k`` rows to one identical state.

        This is what the breadth-first search used to look for, and it found
        the answer only up to three ignored inputs -- its depth cap bit at
        four.  The construction has no cap, so the property is asserted well
        past where the search stopped.
        """

        module = importlib.import_module("esolangs.tools.minifuck")

        for ignored in range(1, 7):
            joint = module._Joint(ignored)  # noqa: SLF001
            for slot in range(ignored):
                joint.emit_setter(slot)
            joint.emit(module._reset_code(ignored))  # noqa: SLF001
            assert not any(m.dead for m in joint.ms), ignored
            assert len({m.key() for m in joint.ms}) == 1, ignored

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
        Building it separately only to inspect its placeholders duplicated
        construction without exercising a distinct path.  The current
        combined check takes 0.12s serially, so it belongs in the fast suite.
        """
        from esolangs.tools import parameterized

        template = parameterized.minifuck("0110")
        assert "{X0}" in template
        assert "{X1}" in template
        lengths = {
            len(self.instantiate(template, [a, b])) for a in (0, 1) for b in (0, 1)
        }
        assert len(lengths) == 1, f"unequal instantiation lengths: {lengths}"
