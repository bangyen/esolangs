"""Covers :mod:`esolangs.tools.minifuck_staged`."""

import importlib
from unittest.mock import patch

import pytest

from esolangs.tools.helpers import essential_inputs
from tests.tools.minifuck_support import _all_derived_plans, _MinifuckCase


class TestMinifuckStaged(_MinifuckCase):
    """The staged route: the enumeration, its index, and the budget that bounds it."""

    # 2.4s: the three-input derivation is the cost.  The staging probe at the
    # unstaged arity is free -- declining is the whole point of it -- so this
    # does not pay for the staged arities above three.
    @pytest.mark.slow
    def test_a_table_with_no_staging_falls_through(self) -> None:
        """An unplanned table declines the staging and reaches the next route.

        Both three-input plans are now complete, so the fall-through is
        exercised at an arity that has no plan at all -- which is the case
        that matters, since it is what lets a wider table reach the sculpted
        route instead of failing outright.

        That arity is now six: four and five are both staged (partially), so
        probing the fall-through at either would miss the point and pay that
        arity's derivation to do it.

        The unstaged arity is read off :data:`_STAGED_ARITIES` rather than
        written down, so raising the staged arity moves this test with it.
        What is asserted is the *gate* -- that an unstaged arity declines
        immediately -- which is what keeps the miss cheap.

        **What is probed is ``_derive_staging``, not ``_staged``.**  With
        :func:`_mux`'s own arity gate gone the fall-through *succeeds*, so
        asserting None on ``_staged`` would be asserting the generator is
        partial: six inputs does build, 1822 characters in about 35 seconds
        for the all-ones table.
        """
        from esolangs.tools import parameterized
        from esolangs.tools.minifuck import (
            _STAGED_ARITIES,
            _derive_staging,
            _staged,
        )

        unstaged = max(_STAGED_ARITIES) + 1
        assert unstaged not in _STAGED_ARITIES
        assert _derive_staging("1" * 2**unstaged, unstaged) is None
        # A table the derivation does reach is built from it, not searched.
        for table_int in range(4):
            key = format(table_int, "08b")
            template = _staged(key, 3)
            assert template is not None, key
            for combo in range(8):
                bits = [(combo >> (2 - i)) & 1 for i in range(3)]
                got = self.run_minifuck(self.instantiate(template, bits))
                assert got == key[combo], f"{key} inputs {bits}"
        # ...and the public entry point still builds one.
        assert parameterized.minifuck("00000001")

    @pytest.mark.slow  # the four-input derivation is whole-arity, minutes
    def test_four_input_xor_builds_from_a_staging(self) -> None:
        """XOR4 builds without searching, and computes its function.

        Four inputs is the arity the insert family was added for, and XOR is
        the pointed case: ``the relevant generator tests`` records it
        as the four-input
        table the searches fail on.  The searches are stubbed to raise, so a
        table that builds here built from a staging.

        Every row is run on the interpreter and the widths are compared: a
        template that computes the table but whose fills differ in length
        leaks its inputs through ``len(program)``, which is the one thing the
        parameterized convention exists to prevent.

        **Only one table.**  This used to build five, and assert besides that
        a plans miss returns None -- which forced a *whole-arity* derivation
        on top of the ordinary one and put the test past nine minutes for
        five builds.  That second sweep (the flipped-embed pass) has since
        been removed outright, but the lever is unchanged: a four-input miss
        still runs the staged enumeration to its caps, so what this costs is
        how much of the arity it demands.  The recorded claim is about XOR4,
        and that is what is kept; the miss path is covered at an unstaged
        arity by :meth:`test_a_table_with_no_staging_falls_through`, which
        pays no derivation at all.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.minifuck")

        table = "0110100110010110"  # XOR4, the recorded search failure
        # The searches these used to stub are gone; assert that structurally
        # instead of patching them, then build as before.
        assert not hasattr(module, "_find_column")
        assert not hasattr(module, "_find_parked")
        assert module._staged(table, 4) is not None  # noqa: SLF001
        template = module.minifuck.__wrapped__(table)
        widths = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            got = self.run_minifuck(program)
            assert got == table[combo], f"{table} inputs {bits}"
        assert len(widths) == 1, widths

    def test_staging_budget_is_counted_in_stagings_not_seconds(self) -> None:
        """The budget is machine-independent, and it ships disabled.

        A wall-clock budget would make this generator non-deterministic: the
        same table would build on a fast host and fall through on a slow
        one, and which template a table got would depend on machine load.
        Counting *stagings* -- one ``(separator, settle, suffix,
        accumulator)`` tuple of :func:`_stagings` -- is identical everywhere,
        so a budget selects the same tables on any hardware.

        Two properties are pinned.  The default is ``None``, because
        anything else would change every recorded template.  And the slice
        order is the plain enumeration order while unbudgeted -- yield
        ordering only applies when something is actually being given up, and
        only at the arity it was measured at.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.minifuck")

        assert module._STAGING_BUDGET is None  # noqa: SLF001

        plain = tuple(
            (sep, settle)
            for sep in range(len(module._SEPS))  # noqa: SLF001
            for settle in (0, 1)
        )
        assert module._slices(4) == plain  # noqa: SLF001
        assert module._slices(3) == plain  # noqa: SLF001

        # The ranking is a permutation of the slices, not a subset: a budget
        # reorders what is spent first, it never drops a slice outright.
        assert sorted(module._SLICE_YIELD_ORDER) == sorted(plain)  # noqa: SLF001

    @pytest.mark.slow
    def test_the_slice_order_is_its_measured_yield(self) -> None:
        """The yield ranking is re-derived, not trusted.

        The comment above ``_SLICE_YIELD_ORDER`` states the measurement
        that produced it -- each slice's yield at four inputs, best 2874
        against worst 424 -- but a stated measurement is not a checked
        one, and the table is dormant as shipped, so nothing else would
        catch it drifting.

        The yield is *marginal*, not intrinsic: a slice is credited with
        the columns it is the first to reach in the plain enumeration,
        not with everything it could place on its own.  That distinction
        is what picks this order out -- ranking slices by their
        independent reach gives a different one -- so the assertion
        pins the mechanism and not just the numbers.  All ten counts are
        distinct, so descending order is total and needs no tie-break.
        """
        import importlib
        from collections import Counter

        module = importlib.import_module("esolangs.tools.minifuck")

        index = module._staging_index(4)  # noqa: SLF001
        counts = Counter((entry[0], entry[1]) for entry in index.values())
        assert len(set(counts.values())) == len(counts), counts
        derived = tuple(sorted(counts, key=lambda slot: -counts[slot]))
        assert derived == module._SLICE_YIELD_ORDER  # noqa: SLF001
        assert max(counts.values()) == 2874
        assert min(counts.values()) == 424

    def test_five_input_budget_uses_its_separate_default(self) -> None:
        """The five-input override is selected only while budgets are off.

        Five inputs were measured separately from the smaller staging passes,
        so its disabled-budget value must not accidentally inherit a future
        finite general budget.  Patch both values to make the dispatch, not
        their current equal ``None`` spelling, observable.
        """
        module = importlib.import_module("esolangs.tools.minifuck_staged")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_STAGING_BUDGET", None)
            patch.setattr(module, "_STAGING_BUDGET_N5", 17)
            assert module._budget(5) == 17  # noqa: SLF001
            assert module._budget(6) == 17  # noqa: SLF001
            assert module._budget(4) is None  # noqa: SLF001

            # A finite general budget applies uniformly, including at five.
            patch.setattr(module, "_STAGING_BUDGET", 23)
            assert module._budget(5) == 23  # noqa: SLF001

    def test_a_budget_gives_up_length_not_coverage(self) -> None:
        """A table the budget skips still builds, through the sculpted route.

        This is the property that makes lowering the budget safe on a slow
        machine: the staged route is what emits *short* templates, and
        :func:`_mux` is total at four inputs, so a budget trades program
        length for time and never coverage.

        Uses a tiny budget and a table the staged route would otherwise
        place, so the fall-through is what is exercised.  Every row is run:
        an emitted template is not evidence it computes.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.minifuck_staged")
        mux = importlib.import_module("esolangs.tools.minifuck_mux")

        table = "0110100110010110"  # XOR4, which the staged route places
        original = module._STAGING_BUDGET  # noqa: SLF001
        try:
            module._STAGING_BUDGET = 1  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derive_staging(table, 4) is None  # noqa: SLF001
            template = mux._mux(table, 4)  # noqa: SLF001
            assert template is not None
        finally:
            module._STAGING_BUDGET = original  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001

        widths = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    # Two seconds of cold derivation.  It used to ride a cache another test
    # in the same file had already filled; in a file of its own it pays for
    # its own, which is the band it was always in.
    @pytest.mark.medium
    def test_a_budget_stops_the_suffix_pass_too(self) -> None:
        """The budget is checked in the insert pass, not only the first one.

        ``test_a_budget_gives_up_length_not_coverage`` above spends the
        budget immediately, so the enumeration stops in the bracket-run loop
        and the suffix pass that follows it never runs.  A budget that
        outlives the first loop and expires inside the second is what proves
        the later checks are wired: without them a budget would be ignored
        for the whole insert pass, which is the more expensive half.

        The table matters as much as the budget.  A table the staged route
        *places* is claimed before the budget can bite, so this uses one the
        enumeration never places -- the sculpted route is what serves it --
        and the spend was measured rather than guessed: the insert pass is
        entered at 7540 stagings and the whole enumeration costs 120640, so
        8000 lands inside it.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.minifuck")

        orphan = "1101000011010000"  # no staging in the enumeration prints it
        original = module._STAGING_BUDGET  # noqa: SLF001
        try:
            module._STAGING_BUDGET = 8000  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derive_staging(orphan, 4) is None  # noqa: SLF001
            # And the oracle, which carries its own copy of both loops: a
            # budget honoured in only one of the two would make the pair
            # disagree for a reason unrelated to the order they exist to pin.
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derived_plans(4, (orphan,)) == {}  # noqa: SLF001
        finally:
            module._STAGING_BUDGET = original  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001

        # And it still builds, by the route that does not need a staging.
        template = module.minifuck(orphan)
        widths = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == orphan[combo], (orphan, bits)
        assert len(widths) == 1, widths

    def test_a_spent_budget_stops_before_the_first_staging(self) -> None:
        """A budget of zero derives nothing at all, in both spellings.

        The exhaustion check runs before the first embed rather than after
        it, so a budget already spent costs nothing rather than one staging.
        Both the oracle and the index it is compared against are asked, since
        each carries its own copy of the loop and a budget honoured in only
        one of them would make the two disagree for a reason unrelated to
        the enumeration order they exist to pin.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.minifuck_staged")

        original = module._STAGING_BUDGET  # noqa: SLF001
        try:
            module._STAGING_BUDGET = 0  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derived_plans(2, ("0110",)) == {}  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._staging_index(2) == {}  # noqa: SLF001

            # One staging's worth spends inside the bracket-run loop instead
            # of before it, which is the other end of the same check: the
            # budget is consumed per staging visited, so a budget of one
            # gets exactly one look before it stops.
            module._STAGING_BUDGET = 1  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001
            assert module._derived_plans(2, ("0001",)) == {}  # noqa: SLF001
        finally:
            module._STAGING_BUDGET = original  # noqa: SLF001
            module._derived_plans.cache_clear()  # noqa: SLF001

    @pytest.mark.slow  # ~3.6s: a five-input index fill plus a sculpted build
    def test_a_table_no_staging_reaches_costs_length_not_coverage(self) -> None:
        """A table outside every staging still builds, the other way.

        A five-input table the tabulation cannot answer is an index miss --
        the linear-algebra screen that used to pre-empt the lookup is gone,
        see the note above ``_CHAIN_CAP`` -- so the danger is not a wrong
        admission but a table that stops being built at all.  This drives
        the miss and the fall-through below it.

        Executed on every row rather than merely emitted, because a miss
        that quietly rerouted a table to a *wrong* program would look
        identical to one that rerouted it to a longer one.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.minifuck")

        table = "01001100001110000110000011001011"
        module._derived_plans.cache_clear()  # noqa: SLF001
        assert module._derive_staging(table, 5) is None  # noqa: SLF001

        template = module.minifuck(table)
        widths = set()
        for combo in range(32):
            bits = [(combo >> (4 - i)) & 1 for i in range(5)]
            program = self.instantiate(template, bits)
            widths.add(len(program))
            assert self.run_minifuck(program) == table[combo], (table, bits)
        assert len(widths) == 1, widths

    def test_only_the_first_separators_are_scanned(self) -> None:
        """The searching routes scan two separators; the plan names the rest.

        Adding a separator to :data:`_SEPS` widens what the plan can *name*
        without widening what the searches must *try* -- each extra separator
        would multiply the cost of every fallback search.  This pins that
        split, which is easy to undo by looping over ``_SEPS`` out of habit.
        """

        from esolangs.tools.minifuck import (
            _SCAN_SEPS,
            _SEPS,
            _stagings,
        )

        assert _SEPS[:2] == _SCAN_SEPS, _SCAN_SEPS
        assert len(_SEPS) > len(_SCAN_SEPS), _SEPS
        # Every separator index the enumeration yields must exist, and it
        # must offer all of them -- the ten stragglers that need separators
        # past the scanned pair are the whole reason ``_SEPS`` is wider.
        offered = {sep_index for sep_index, *_rest in _stagings(3)}
        assert offered == set(range(len(_SEPS))), offered

    @pytest.mark.parametrize(("sep_index", "settle"), [(2, 0), (0, 1)])
    def test_closed_sweeps_match_the_emit_and_walk_sweep(
        self, sep_index: int, settle: int
    ) -> None:
        """The derived accumulator sweeps equal the interpreter's, per suffix.

        ``_staging_index`` fills from ``_closed_sweeps``, which computes each
        staging's columns arithmetically -- the bracket staircase, the
        slice-constant pool, the walk-out XOR -- where ``_column_sweep``
        emits the pool code and walks.  The index-vs-oracle tests compare
        the two end to end; this is the direct per-suffix pin, at the first
        arity with the insert family, so a formula that drifts is named by
        the ``(slice, suffix, orientation)`` it breaks on rather than by a
        reassigned staging three layers up.

        Two slices rather than ten to stay in the fast suite; the full
        cross-check behind the closed form ran every slice at two, three
        and four inputs -- 10440 sweeps -- with no disagreement.  The
        slices chosen span both settles and include the one five-input XOR
        builds from.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.minifuck")

        chains, pools = module._slice_chains(4, sep_index, settle)  # noqa: SLF001
        base = module._embed(  # noqa: SLF001
            4,
            settle=settle,
            sep=module._SEPS[sep_index],  # noqa: SLF001
        )
        module._clamp(base)  # noqa: SLF001
        module._walk_to(base, module._BASE - 1)  # noqa: SLF001
        suffixes: list[int | str] = list(range(module._MAX_BRACKETS + 1))  # noqa: SLF001
        suffixes += list(module._insert_suffixes())  # noqa: SLF001
        run = base.fork()
        for suffix in suffixes:
            if isinstance(suffix, int):
                staged = run.fork()
                staged.emit("<")
                run.emit("[")
            else:
                staged = base.fork()
                staged.emit(suffix)
            module._clamp(staged)  # noqa: SLF001
            derived = module._closed_sweeps(chains, pools, suffix)  # noqa: SLF001
            for cell7 in (0, 1):
                walked = module._column_sweep(staged, cell7)  # noqa: SLF001
                assert derived[cell7] == walked, (sep_index, settle, suffix, cell7)

    def test_the_staging_index_agrees_with_the_enumeration(self) -> None:
        """The inverted index assigns exactly what the per-table sweep does.

        ``_derive_staging`` reads ``_staging_index``, which walks the
        enumeration once per arity and tabulates column -> first staging;
        ``_derived_plans`` walks the same order per table.  They must agree
        tuple for tuple, because the order -- not a stored answer -- is what
        decides which program a truth table gets.

        The regression net for one mistake that is hard to catch: an index
        walking the order wrongly still produces columns that are reachable
        and valid.  A draft interleaved the two enumeration passes per slice
        instead of running every pure bracket run before any insert suffix,
        and the only symptom was five-input XOR assigned ``None`` where the
        enumeration assigns ``(2, 0, 0, 33)`` -- every program it emitted
        still printed its table.  So the assertion is on the staging
        *tuple*, never on whether the build works.

        ``_derived_plans`` takes a *tuple* of targets and answers them in one
        walk, so 256 separate three-input walks (7.4s) become one (0.12s).
        The complement is dropped from the targets because at these arities
        it is already in the set.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.minifuck")

        for arity in (2, 3):
            index = module._staging_index(arity)  # noqa: SLF001
            width = 2**arity
            tables = tuple(format(value, f"0{width}b") for value in range(2**width))
            plans = module._derived_plans(arity, tables)  # noqa: SLF001
            for table in tables:
                column = tuple(int(bit) for bit in table)
                assert index.get(column) == plans.get(table), (arity, table)

    @pytest.mark.slow  # ~22s: the arity 4 and 5 index builds dominate
    def test_the_staging_index_agrees_at_the_wider_arities(self) -> None:
        """The same agreement where the insert family and the budget live.

        Four inputs is the first arity with a second enumeration pass (the
        insert suffixes), and five is the only one that runs under a staging
        budget and in slice-yield rather than plain order.  Both are code
        paths the two- and three-input check above never reaches, and both
        are where an index that mis-walks the order would show up.

        Batched for the same reason as the check above: ``_derived_plans``
        answers a whole tuple of targets in one walk, so the sample costs one
        four-input enumeration instead of one per table -- 97s of per-table
        calls against 2.6s for the single walk, to the same answers.  The
        complements go into the targets explicitly here, because a 40-table
        sample at arity 4 does not already contain them the way the
        exhaustive arities above do.

        What is left is the oracle's emit-and-walk enumerations -- the index
        builds themselves derive their columns in closed form and cost 0.62s
        and 1.12s -- and the oracle is the independent spelling this test
        exists to compare against, not overhead the test can drop.  So it
        stays marked slow.
        """
        import importlib
        import random

        module = importlib.import_module("esolangs.tools.minifuck")

        random.seed(20260902)
        wide = [format(value, "016b") for value in range(65536)]
        wide = [t for t in wide if len(essential_inputs(t, 4)) == 4]
        samples = [(4, t) for t in random.sample(wide, 40)]
        samples.append((4, "0110100110010110"))  # four-input XOR
        samples.append((5, "01101001100101101001011001101001"))  # five-input

        by_arity: dict[int, list[str]] = {}
        for arity, table in samples:
            by_arity.setdefault(arity, []).append(table)

        for arity, tables in by_arity.items():
            index = module._staging_index(arity)  # noqa: SLF001
            targets = set(tables)
            for table in tables:
                targets.add("".join(str(1 - int(bit)) for bit in table))
            plans = module._derived_plans(arity, tuple(sorted(targets)))  # noqa: SLF001
            for table in tables:
                column = tuple(int(bit) for bit in table)
                assert index.get(column) == plans.get(table), (arity, table)

    def test_the_staging_enumeration_is_offered_only_at_its_arities(self) -> None:
        """Outside ``_STAGED_ARITIES`` the derivation offers nothing.

        One input is solved by the degenerate route and four is past what the
        enumeration covers, so neither asks for a staging.  The guard is what
        lets the caller fall through to the searches rather than paying an
        enumeration that has no entries to give.
        """

        from esolangs.tools.minifuck import (
            _STAGED_ARITIES,
            _derive_staging,
            _derived_plans,
        )

        for n in (1, max(_STAGED_ARITIES) + 1):
            assert n not in _STAGED_ARITIES
            assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, n) == {}
            assert _derive_staging("0" * 2**n, n) is None
        # At a staged arity the enumeration really does have entries, so the
        # empty results above are the guard and not an exhausted search.
        assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, 2)

    @pytest.mark.slow  # re-simulates a derived staging for every table
    def test_stagings_deliver_the_column_the_read_sees(self) -> None:
        """Every staging really does deliver its table's column at the read.

        This recomputes what a staging leaves at its accumulator *as the read
        sees it* -- after the pool code and the walk out, which is where the
        running prefix-XOR applies -- and checks it against the table it was
        derived for.  Selecting on the pre-walk column instead is the mistake
        that covered 10 of 16 at two inputs, so the transform is the point
        rather than an implementation detail.

        The derivation accepts a staging by *printing*, which is a stronger
        test than this one and would catch a broken staging on its own.  What
        this adds is the reason: it pins that the column arrives at the read,
        so a future change that made the printing accidental rather than
        earned would show up here.

        ``01101101`` used to be listed here as the table only the two-insert
        family reached.  That family is gone and the sculpted route builds
        the pair instead, so the table has no staging to check -- it is not
        an omission, and adding it back would assert on a route that no
        longer produces stagings at all.
        """

        from esolangs.tools.minifuck import (
            _BASE,
            _SEPS,
            _clamp,
            _derive_staging,
            _embed,
            _find_pool,
            _walk_to,
        )

        plans = {
            2: {
                format(t, "04b"): _derive_staging(format(t, "04b"), 2)
                for t in range(16)
            },
            3: {
                key: _derive_staging(key, 3)
                for key in ("00000001", "01111111", "00010111")
            },
        }
        for n, plan in sorted(plans.items()):
            for key, staging in sorted(plan.items()):
                assert staging is not None, (n, key)
                sep_index, settle, suffix, acc = staging
                joint = _embed(
                    n,
                    settle=settle,
                    sep=_SEPS[sep_index],
                )
                _clamp(joint)
                _walk_to(joint, _BASE - 1)
                joint.emit("[" * suffix + "<" if isinstance(suffix, int) else suffix)
                _clamp(joint)
                arrived = None
                for cell7 in (0, 1):
                    probe = joint.fork()
                    code = _find_pool(probe, cell7, acc - 1)
                    if code is None:
                        continue
                    probe.emit(code)
                    _walk_to(probe, acc - 1)
                    column = "".join(str(b) for b in probe.col(acc))
                    complement = "".join(str(1 - int(c)) for c in column)
                    if key in (column, complement):
                        arrived = column
                        break
                assert arrived is not None, (n, key, sep_index, settle, suffix, acc)

    def test_the_enumeration_and_the_derivation_agree(self) -> None:
        """``_stagings`` states the order ``_derived_plans`` actually walks.

        The derivation interleaves the four loops with the machines it is
        advancing, so a bracket count costs one instruction rather than a
        rebuild -- which means the order is written out twice, once as a
        generator and once as nested loops.  This checks they match, since a
        drift between them would silently change which staging each table
        gets while every other test still passed.
        """

        from esolangs.tools.minifuck import (
            _MAX_ACC,
            _MAX_BRACKETS,
            _SEPS,
            _STAGED_ARITIES,
            _derived_plans,
            _insert_suffixes,
            _stagings,
        )

        expected = [
            (sep_index, settle, brackets, acc)
            for sep_index in range(len(_SEPS))
            for settle in (0, 1)
            for brackets in range(_MAX_BRACKETS + 1)
            for acc in range(9, _MAX_ACC + 1)
        ]
        assert list(_stagings(3)) == expected
        # Every staging the derivation hands back is one the enumeration
        # offers -- so the caps and the loops cannot have drifted apart.
        offered = set(expected)
        for table, staging in _all_derived_plans(
            _derived_plans, _STAGED_ARITIES, 2
        ).items():
            assert staging in offered, (table, staging)

        # Four inputs adds the insert family as a *second pass*, after every
        # pure run: that ordering is what keeps the arities the pure runs
        # already close assigned exactly the stagings they had, so it is
        # checked rather than assumed.  The derivation writes this order out
        # a second time as nested loops, which is what can drift.
        widened = expected + [
            (sep_index, settle, suffix, acc)
            for sep_index in range(len(_SEPS))
            for settle in (0, 1)
            for suffix in _insert_suffixes()
            for acc in range(9, _MAX_ACC + 1)
        ]
        assert list(_stagings(4)) == widened
        assert widened[: len(expected)] == expected

    # 4.8s: the enumeration it walks is the cost.
    @pytest.mark.slow
    def test_the_enumeration_skips_a_column_that_is_not_one_digit(self) -> None:
        """A probe printing anything but single digits is passed over.

        Measured over ``_derived_plans(2)``, all 1844 prints the enumeration
        makes are single digits, so this filter never fires on the stagings
        that exist -- it is what keeps a column from being *decoded* out of a
        print the endgame did not actually produce one digit per row for.
        Forcing it needs the print itself stubbed, and the caches cleared
        either side so neither the stub nor the real run is served stale.
        """

        from esolangs.tools.minifuck import (
            _STAGED_ARITIES,
            _derived_plans,
            _Joint,
        )

        real_printed = _Joint.printed

        def two_digits(self: object) -> list[str]:
            # Every row prints two characters, so no column is ever decoded.
            return ["00" for _ in real_printed(self)]

        try:
            _derived_plans.cache_clear()
            with patch.object(_Joint, "printed", two_digits):
                assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, 2) == {}
        finally:
            _derived_plans.cache_clear()
        # With the real print restored the enumeration finds its entries
        # again, so the empty result above is the filter and not a cache.
        assert _all_derived_plans(_derived_plans, _STAGED_ARITIES, 2)
