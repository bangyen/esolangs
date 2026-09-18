"""Covers :mod:`esolangs.tools.pct_fold` and :mod:`esolangs.tools.pct_fold_plan`."""

import importlib
import itertools
from types import ModuleType

import pytest

from esolangs.tools.helpers import TEMPLATE_CHAR, runs
from tests.tools.pct_support import _fold_clean_amount, _fold_rule_move, _fold_step


def _run_spans(module: ModuleType, template: str) -> list[tuple[int, int]]:
    """The ``[start, end)`` of each input's run in the template's body.

    ``runs`` consumes the runs left to right in the header's setter order
    and refuses a run of the wrong width or a stray, so a span per input
    is the runs in stream order, each as wide as its setter.
    """
    return runs(module.body(template), TEMPLATE_CHAR, module.setters(template))


class TestPctInterleavedFold:
    """The staged replacement emits real code between its runs."""

    def test_interleaved_template_replays_every_three_input_row(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run

        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        table = "00001111"  # X1 creates equal suffix cofactors before X2
        template = module._interleaved_fold(table, 3)  # noqa: SLF001
        assert template is not None
        # Runs remain in stream order even when a stage coalesces directly
        # through equal branches instead of needing a relocation.
        assert len(_run_spans(module, template)) == 3
        for row, want in enumerate(table):
            bits = [(row >> 2) & 1, (row >> 1) & 1, row & 1]
            io = ScriptedIO()
            run(module.fill(template, bits), io)
            assert io.getvalue() == want

    # Split by cost, measured: the 256 builds are 0.28s and the 1088
    # interpreter replays are 5.15s.  The build sweep carries the contract a
    # mutant can break -- the selective count, decline-is-None, slot order --
    # so it stays in the fast run, and the exhaustive replay moves to the
    # slow-marked sibling below.  Splitting rather than sampling keeps the
    # whole 256-table space on the route-reaching half.
    def test_every_three_input_table_builds_or_declines_exactly(self) -> None:
        """Sweep all 256 three-input tables through the staged build.

        One table exercises one route; the whole space is what reaches the
        merge, split and refusal arms, and it is the only way to hold the
        two outcomes to their contracts at once.  A decline must be exactly
        ``None``, never a partial template a caller might emit.  That a
        build *computes* its table is the sibling's job.
        """
        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        built = 0
        for value in range(256):
            table = format(value, "08b")
            template = module._interleaved_fold(table, 3)  # noqa: SLF001
            if template is None:
                continue
            built += 1
            assert len(_run_spans(module, template)) == 3, table  # stream order
        # The route is selective by design -- it runs before the all-row
        # fallback -- so pin that it neither builds everything nor nothing.
        assert built == 136

    @pytest.mark.slow  # ~5s: 1088 interpreter replays
    def test_every_three_input_build_computes_its_table(self) -> None:
        """Every table the route builds is replayed row by row.

        A template that computes the wrong table is worse than a decline, so
        the rows are checked on the interpreter rather than the shape being
        trusted.  The build half runs in the fast loop; this is the half that
        costs interpreter time.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run

        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        for value in range(256):
            table = format(value, "08b")
            template = module._interleaved_fold(table, 3)  # noqa: SLF001
            if template is None:
                continue
            for row, want in enumerate(table):
                bits = [(row >> 2) & 1, (row >> 1) & 1, row & 1]
                io = ScriptedIO()
                run(module.fill(template, bits), io)
                assert io.getvalue() == want, (table, row)

    @pytest.mark.slow  # ~10s: 4096 four-input builds
    def test_four_input_tables_build_or_decline_without_raising(self) -> None:
        """At four inputs the merge has room to act, so its arms are reached here.

        Build-only on a stride: what is under test is that every table
        either yields a well-formed template or declines cleanly.  A raise
        would mean the planner emitted a move its own algebra refuses,
        which is the failure the guards exist to prevent, and no amount of
        row replay would reveal it if the build never returned.
        """
        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        built = 0
        for value in range(0, 2**16, 16):
            table = format(value, "016b")
            template = module._interleaved_fold(table, 4)  # noqa: SLF001
            if template is None:
                continue
            built += 1
            assert len(_run_spans(module, template)) == 4, table
        assert built == 1444

    def test_interleaved_fallback_builds_past_the_all_row_ladder(self) -> None:
        """A late-ignored suffix stays compact instead of spending 4096 rungs.

        Rows are *sampled* on a stride, as at eleven inputs above: the build
        itself is instant, and all 4096 rows through the interpreter were
        seven seconds of this module's budget for one table.  The stride is
        coprime to the arity's runs and covers all four values of the two
        bits the table actually reads, so every branch of the answer is
        still executed -- the suffix is ignored by construction, which is
        the property under test.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run

        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        n = 12
        # XOR of the first two bits: it is neither a cascade subcube nor a
        # threshold, and the all-row fold cannot lay its 4096 positions.
        table = "".join("0110"[row >> (n - 2)] for row in range(2**n))
        assert module._fold(table, n) is None  # noqa: SLF001
        template = module.pct_squared_minus_one(table)
        seen = set()
        for row in range(0, 2**n, 97):
            bits = [(row >> shift) & 1 for shift in range(n - 1, -1, -1)]
            io = ScriptedIO()
            run(module.fill(template, bits), io)
            assert io.getvalue() == table[row], f"row {row}"
            seen.add(row >> (n - 2))
        assert seen == {0, 1, 2, 3}, seen


class TestPctFoldEmitter:
    """The emitter's mirror, driven at the steps the planner rarely asks for.

    :class:`_FoldEmitter` tracks every row's accumulator exactly, so its
    moves can be checked as arithmetic: build one over a small table and
    read ``pos`` before and after.  ``s`` subtracts 2 and ``i`` subtracts
    3, and ``p`` negates, so a rise is spelled as a negated descent.
    """

    @staticmethod
    def emitter(table: str = "01", n: int = 1):
        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        return module._FoldEmitter(table, n)  # noqa: SLF001

    def test_a_zero_step_emits_nothing(self) -> None:
        """Moving by zero is not spelled at all, in either direction."""
        for move in ("descend", "plain_rise"):
            em = self.emitter()
            getattr(em, move)(0)
            assert em.body == []

    def test_a_single_step_is_spelled_as_three_against_two(self) -> None:
        """One has no spelling of its own: ``s`` is 2 and ``i`` is 3.

        So a step of 1 is a step of 3 the other way against a step of 2
        back -- the only combination of the two primitives that lands one
        away.  Both directions net exactly one, and every row moves
        together, since the accumulator is shared.
        """
        em = self.emitter()
        before = dict(em.pos)
        em.descend(1)
        assert em.body == ["i", "psp"]
        assert all(em.pos[r] - before[r] == -1 for r in before)

        em = self.emitter()
        before = dict(em.pos)
        em.plain_rise(1)
        assert em.body == ["pip", "s"]
        assert all(em.pos[r] - before[r] == 1 for r in before)

    def test_a_single_class_finishes_on_its_digit_from_anywhere(self) -> None:
        """One class: ``finish`` erases the point and shifts to the byte.

        A constant table's rows may sit anywhere in the window when the
        endgame runs; ``'`` puts them all on zero, and one shift of 48 or
        49 lands the digit, so the mirror reads the digit itself whatever
        the start.
        """
        for start in (0, 2900, -2900):
            em = self.emitter("0", 0)
            key = next(iter(em.pos))
            em.load({key: (start, "0")})
            em.finish()
            assert em.pos[key] == 48
            assert em.body == ["'p" + "i" * 16 + "p", "e"]

    def test_a_rise_with_no_headroom_preshifts_first(self) -> None:
        """``p`` needs two to work with, so a shorter rise makes room.

        The rise is ``p``, a subtraction, ``p``, and the subtraction has
        no spelling below 2.  When the victims sit so high that the
        relocation leaves less than that, the emitter drops everything
        first and recomputes the distance from the new bottom.  A victim
        one lower needs no preshift, which is what separates the two.
        """
        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        limit = module._LIMIT  # noqa: SLF001

        def rise_from(victim_top: int) -> list[str]:
            em = self.emitter()
            keys = list(em.pos)
            em.load({keys[0]: (victim_top, "0"), keys[1]: (-10, "1")})
            em.rise(limit + 1, frozenset({keys[0]}))
            return em.body

        # u == 1: below the floor, so a preshift of 1 is spelled first.
        assert rise_from(limit) == ["i", "psp", "psp", "s"]
        # u == 2: exactly the floor, so the rise is spelled on its own.
        assert rise_from(limit - 1) == ["psp", "s"]

    def test_a_rise_with_no_survivors_takes_the_fallback_window(self) -> None:
        """Wiping every point leaves no gap to measure, so the window is 40.

        The everything-wipe the planner emits is a dive, so this is the one
        place the rise's fallback is exercised: the point goes over the
        limit, is flushed by the ``s``, and lands at -2.
        """
        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        em = self.emitter("0", 0)
        key = next(iter(em.pos))
        em.rise(module._LIMIT + 1, frozenset({key}))  # noqa: SLF001
        assert em.body == ["p" + "i" * 1000 + "ss" + "p", "s"]
        assert em.pos == {key: -2}


class TestPctFoldMoves:
    """The fold's move generator, at the guards that refuse a relocation.

    A ``_FoldPoint`` is ``(top, span, class, ids)`` and a state is a tuple
    of them.  The guards below are properties of the arithmetic, so they
    are driven with states built by hand: the spacings involved are wider
    than any table's own starting layout, which is four per run.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.pct_squared_minus_one")

    def test_a_collision_across_classes_is_not_a_merge(self) -> None:
        """Two points at one value are indistinguishable forever after.

        So a collision is legal only within a class -- and only between
        points already wiped, since a group with extent has rows at
        several values and an equal top is not an equal anything.
        """
        module = self.module()
        merge = module._fold_merge  # noqa: SLF001

        cross = [(0, 0, "0", frozenset({0})), (0, 0, "1", frozenset({1}))]
        assert merge(cross) is None

        extent = [(0, 0, "0", frozenset({0})), (0, 3, "0", frozenset({1}))]
        assert merge(extent) is None

        legal = [(0, 0, "0", frozenset({0})), (0, 0, "0", frozenset({1}))]
        assert merge(legal) == ((0, 0, "0", frozenset({0, 1})),)

    def test_a_survivor_reaching_below_the_victims_offers_no_window(self) -> None:
        """The relocation window is the gap to the nearest survivor's bottom.

        A survivor whose span reaches down past the victims' top closes
        that gap entirely, so there is no amount to relocate by and the
        dive is skipped rather than spelled.  Both the ascending and the
        descending half apply the same rule.
        """
        state = (
            (0, 400, "0", frozenset({0})),
            (-100, 0, "0", frozenset({1})),
            (-200, 0, "1", frozenset({2})),
        )
        assert len(list(self.module()._fold_moves(state, kcap=3))) == 1  # noqa: SLF001

    def test_a_relocation_that_would_overflow_the_span_is_skipped(self) -> None:
        """Every wipe caps the spread, so a move that widens it is refused.

        Two survivors far from *each other* are what reaches this: the
        near one bounds how far the state may travel, and the far one is
        still far after travelling that distance.  The guard is what keeps
        the yielded states inside the accumulator's range, so it is
        checked on the output rather than only executed.
        """
        module = self.module()
        state = (
            (0, 0, "0", frozenset({0})),
            (-10, 0, "1", frozenset({1})),
            (-12000, 0, "0", frozenset({2})),
        )
        moves = list(module._fold_moves(state, kcap=3))  # noqa: SLF001
        assert moves, "the positive control must offer some move"
        for *_rest, nxt in moves:
            hi = max(p for p, _, _, _ in nxt)
            lo = min(p - span for p, span, _, _ in nxt)
            assert hi - lo <= 2 * module._LIMIT  # noqa: SLF001


class TestPctFoldPlanners:
    """The rule construction's refusals, driven through their own guards.

    :func:`_fold_reduce` runs the case analysis of ``_fold_rule_move`` to a
    ``done`` state.  It answers ``None`` rather than raising when no rule
    applies or the budget runs out, so the refusals are reachable without
    contriving an unsolvable table.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.pct_squared_minus_one")

    #: Four points, alternating classes: not already finished, and small
    #: enough that the rules answer quickly.
    STATE = (
        (0, 0, "0", frozenset({0})),
        (-4, 0, "1", frozenset({1})),
        (-8, 0, "0", frozenset({2})),
        (-12, 0, "1", frozenset({3})),
    )

    def test_the_reduction_gives_up_on_its_budget(self) -> None:
        """A budget of zero takes no step and answers ``None``.

        The default budget is derived from the state and is a latency
        guard the corpus never reaches; passing one drives the refusal
        without a state the rules genuinely dead-end on.
        """
        module = self.module()

        done = module._fold_done  # noqa: SLF001
        assert module._fold_reduce(self.STATE, done, budget=0) is None  # noqa: SLF001

    def test_the_reduction_finishes_when_it_is_given_room(self) -> None:
        """The positive control: the refusal above is the budget.

        Without this a ``None`` could just as well mean the state was
        malformed, or that no rule ever applies to it.
        """
        module = self.module()

        ops = module._fold_reduce(self.STATE, module._fold_done)  # noqa: SLF001
        assert ops is not None
        state = module._fold_norm(list(self.STATE))  # noqa: SLF001
        for op in ops:
            state = _fold_step(state, op)
            assert state is not None
        # The reduction stops at a threshold state -- one class wholly below
        # the other, which is what the endgame prints from -- rather than
        # going on to one point per class.
        classes = [cls for _, span, cls, _ in state if span == 0]
        assert len(classes) == len(state)
        assert sum(a != b for a, b in itertools.pairwise(classes)) <= 1
        assert not module._fold_done(state)  # noqa: SLF001

    def test_no_rule_applies_to_a_walled_state(self) -> None:
        """Spans that fill the workspace leave the case analysis empty.

        Two groups whose extents nearly fill the workspace offer no legal
        wipe in either direction -- the gap ``q1`` is negative both ways --
        and the spread is past the doubling bound, so every case falls
        through and the move is ``None``.
        """
        stuck = (
            (0, 3000, "0", frozenset({0})),
            (-10, 3000, "1", frozenset({1})),
        )
        assert _fold_rule_move(stuck) is None

    def test_a_step_the_state_does_not_offer_answers_none(self) -> None:
        """``_fold_step`` re-checks a move rather than trusting it.

        An amount outside the window, a wipe with mixed-class victims, and
        an everything-wipe on a two-class state are each refused, so an op
        that was never legal cannot be applied by accident.
        """
        outside = ("d", 1, 99999, frozenset({3}))
        assert _fold_step(self.STATE, outside) is None
        mixed = ("d", 2, 3004, frozenset({2, 3}))
        assert _fold_step(self.STATE, mixed) is None
        everything = ("d", 4, 3004, frozenset({0, 1, 2, 3}))
        assert _fold_step(self.STATE, everything) is None

    def test_a_landing_on_the_other_class_is_refused(self) -> None:
        """A wipe whose landing coincides with an opposite-class point is no move.

        Two points at one value are one point forever, so the algebra refuses
        the collision; the same amount onto a same-class point is the merge.
        """
        onto = ("d", 1, 3004, frozenset({1}))
        cross = ((0, 0, "0", frozenset({0})), (-3004, 0, "1", frozenset({1})))
        assert _fold_step(cross, onto) is None
        same = ((0, 0, "1", frozenset({0})), (-3004, 0, "1", frozenset({1})))
        assert _fold_step(same, onto) == ((0, 0, "1", frozenset({0, 1})),)

    def test_a_clean_amount_skips_an_occupied_landing(self) -> None:
        """The first collision-free amount is computed, not the minimum.

        A survivor sitting exactly 3004 above the victims occupies the
        window's first value, so the clean amount is 3005 -- landing there
        would be a merge the algebra refuses when the classes differ.
        """
        state = (
            (0, 0, "1", frozenset({0})),
            (-3004, 0, "0", frozenset({1})),
        )
        assert _fold_clean_amount(state, "d", 1) == 3005


class TestPctFoldPlan:
    """The plan's rotation pre-pass, and the bound that refuses a table.

    ``_fold_plan`` wipes every group that still has extent before the
    rules run, because a group with extent cannot be a collision target.
    The pre-pass stops on its own when no such wipe is on offer.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.pct_fold")

    def test_the_pre_pass_stops_when_no_bottom_wipe_is_offered(self) -> None:
        """Extent that no minimum-relocation wipe can clear ends the plan.

        Two groups whose spans nearly fill the workspace leave no room for
        the relocation a wipe needs, so the pre-pass breaks out with the
        extent still there and the rules that follow have nothing to
        work with.  The answer is ``None``, not a partial plan.
        """
        stuck = (
            (0, 3000, "0", frozenset({0})),
            (-10, 3000, "1", frozenset({1})),
        )
        assert self.module()._fold_plan(stuck) is None  # noqa: SLF001

    def test_the_pre_pass_clears_extent_when_it_can(self) -> None:
        """The positive control: ordinary extent is wiped and descends.

        Three groups with room around them plan normally, so the refusal
        above is the geometry and not the presence of extent.
        """
        ok = (
            (0, 8, "0", frozenset({0, 1, 2})),
            (-40, 8, "1", frozenset({3, 4, 5})),
            (-80, 8, "0", frozenset({6, 7, 8})),
        )
        plan = self.module()._fold_plan(ok)  # noqa: SLF001
        assert plan is not None
        assert plan

    def test_a_reduction_that_cannot_finish_leaves_the_plan_empty(self) -> None:
        """The pre-pass can clear extent the rules still cannot use.

        Here the wipes run to completion but the reduction that follows
        reaches no two-point state -- every case of the rule analysis
        falls through -- so the whole plan is ``None`` and the caller
        moves on to the next construction rather than emitting a partial
        one.
        """
        state = (
            (-40, 0, "0", frozenset({0})),
            (-48, 0, "1", frozenset({1})),
            (-3048, 8, "1", frozenset({2})),
            (-3448, 4, "0", frozenset({3})),
            (-3452, 400, "1", frozenset({4})),
        )
        assert self.module()._fold_plan(state) is None  # noqa: SLF001

    def test_a_table_too_wide_for_the_workspace_is_refused(self) -> None:
        """The ladder must fit the workspace, and the unit one fits longest.

        The emitter lays the rows from a zero accumulator, so a ladder has to
        fit ``[-_LIMIT, 0]`` -- not the ``2 * _LIMIT`` span a *relative*
        plan state may occupy.  Checking only the latter lets the planner spend
        thousands of moves on a geometry the emitter refuses on its first op.

        Which ladder is offered sets the reach.  The distinct ladders spend
        ``step * (2**n - 1)`` and give out at ten, eleven and twelve inputs
        for steps 4, 2 and 1.  Twelve exceeds even the unit step, so no
        distinct ladder is offered and the fold refuses a table that is not
        symmetric under any mask.
        """
        module = self.module()
        limit = module._LIMIT  # noqa: SLF001

        # Each ladder in turn gives out one arity later than the last.
        assert limit < module._FOLD_STEP * (2**10 - 1)  # noqa: SLF001
        assert limit < module._FOLD_NARROW_STEP * (2**11 - 1)  # noqa: SLF001
        assert 2**11 - 1 <= limit < 2**12 - 1

        # Nothing lays twelve inputs apart, so the fold declines a table no
        # mask collapses: ``x0 xor x1`` has both classes at every Hamming
        # weight past the first under any of the four masks tried there.
        wide = "".join(str(((r >> 11) & 1) ^ ((r >> 10) & 1)) for r in range(2**12))
        assert all(
            not module._ladder_legal(wide, 12, weights, mask)  # noqa: SLF001
            for weights, mask in module._fold_ladders(wide, 12)  # noqa: SLF001
            if weights == (1,) * 12
        )
        assert module._fold(wide, 12) is None  # noqa: SLF001
        # A table inside the bound still builds, so the ``None`` above is
        # the workspace and not the arity itself.
        assert module._fold("0011", 2) is not None  # noqa: SLF001

    def test_the_packed_ladder_meets_the_distinctness_floor(self) -> None:
        """``2**n + 1`` is the least a distinct-position ladder can span.

        The ``2**n`` subset sums are distinct non-negative integers, so the
        largest is at least ``2**n - 1``.  The minimum weight is 2 -- ``2a +
        3b`` cannot spell 1 -- so no subset sums to 1, and by symmetry none
        sums to ``S - 1``; two values inside ``[0, S]`` are unattainable and
        ``S >= 2**n + 1``.  The shipped ladder meets that exactly, which is
        what buys the arity over a uniform one.
        """
        module = self.module()
        assert module._sub_code(1) is None  # noqa: SLF001
        for n in range(2, 12):
            weights = module._fold_subset_weights(n)  # noqa: SLF001
            assert weights is not None
            assert sum(weights) == 2**n + 1, n
            assert min(weights) >= 2, n
            positions = module._fold_positions(n, weights)  # noqa: SLF001
            assert len(set(positions)) == 2**n, n

    def test_the_ladder_refuses_past_eleven_inputs_on_the_span(self) -> None:
        """``_fold_subset_weights`` refuses once its floor exceeds ``_LIMIT``.

        The floor is ``2**n + 1`` (the previous test); the gate is
        ``sum(weights) <= _LIMIT``.  ``_LIMIT`` is not a generator dial --
        it is the interpreter's own over-3003 reset
        (``register_based/pct_squared_minus_one.py``'s ``_reset``,
        mirrored here so planning matches execution), so no decomposition
        of the ladder (one ladder over all ``n`` inputs, or a prefix ladder
        plus a second one over the rest) can seat more than
        ``floor(log2(_LIMIT)) `` ~ 11 inputs at unit gaps: the floor is a
        property of the *span*, and laying a second ladder on top of the
        first still needs the same ``2**n + 1`` distinct positions in
        total, not less, wherever the ``n`` weights are split.  Eleven
        fits (``2**11 + 1 = 2049 <= 3003``); twelve does not
        (``2**12 + 1 = 4097 > 3003``).
        """
        module = self.module()
        assert module._LIMIT == 3003  # noqa: SLF001
        assert module._fold_subset_weights(11) is not None  # noqa: SLF001
        assert module._fold_subset_weights(12) is None  # noqa: SLF001
        assert module._fold_subset_weights(13) is None  # noqa: SLF001

    @pytest.mark.parametrize("ladder", ["narrow", "packed"])
    def test_ladder_setters_are_equal_width(self, ladder: str) -> None:
        """Both branches match in width, and odd-width amounts are respelled.

        The identity has no odd-width spelling, so an amount whose cheapest
        subtraction is one character (2, spelled ``"s"``) can never be padded
        to match a hold and is respelled wider instead.  Both ladders contain
        such an amount.  Checked by execution, not by reading the spelling.
        """
        module = self.module()
        n = 6
        weights = (
            module._fold_uniform(n, module._FOLD_NARROW_STEP)  # noqa: SLF001
            if ladder == "narrow"
            else module._fold_subset_weights(n)  # noqa: SLF001
        )
        assert weights is not None
        setters = module._fold_setters(n, weights)  # noqa: SLF001
        assert len(setters) == n
        for zero, one in setters:
            assert len(zero) == len(one)
            assert module._apply(0, zero) == 0  # noqa: SLF001
        # The whole chain lays every row exactly where the ladder says.
        positions = module._fold_positions(n, weights)  # noqa: SLF001
        for row in (0, 1, 2, 2**n - 1):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            code = "".join(setters[i][bits[i]] for i in range(n))
            assert module._apply(0, code) == positions[row]  # noqa: SLF001

    def test_every_setter_amount_past_the_reset_line_spells(self) -> None:
        """Amounts at and above the reset line respell by descending.

        The overshoot respelling negates, so from 3002 up it leaves the
        accumulator above the 3003 reset: the reset zeroes it and the
        add-back nets ``+k`` rather than ``-amount``.  All 1504 amounts in
        3002..6008 failed that way and *raised* instead of declining, which
        ``_interleaved_fold`` reaches through ``span + 2`` once the spread
        hits 3000.  A pure ``s``/``i`` descent never rises, so it has no
        such ceiling.

        The whole range a setter can be asked for is checked, since
        positions span ``+-_LIMIT``: the widest gap is 6006 and the caller
        adds 2.  Boundaries are checked by execution.
        """
        module = self.module()
        limit = module._LIMIT  # noqa: SLF001
        for amount in (3002, 3003, 3006, 6006, 2 * limit + 2):
            zero, one = module._fold_setters(1, (amount,))[0]  # noqa: SLF001
            assert len(zero) == len(one), amount
            assert module._apply(0, zero) == 0, amount  # noqa: SLF001
            assert module._apply(0, one) == -amount, amount  # noqa: SLF001

    @pytest.mark.slow  # ~5s: ten inputs, 1024 rows filled and run
    def test_a_low_run_ten_input_table_builds_and_runs(self) -> None:
        """A low-run ten-input table takes the skeleton path, and lays.

        This is the regression the ladder gate closed.  ``x0 ^ x1`` widened
        to ten inputs has three runs, so it is no subcube (the cascade
        misses) and reaches the fold, where ``_fold_construct``'s ``r <= 5``
        skeletons plan it in three ops.  Those skeletons were mined on the
        wide ladder, whose ten-input span is 4092 against a 3003-value
        workspace -- so the emitter could not lay the plan, and the build
        died on a bare ``AssertionError`` rather than building or refusing.

        On the narrow ladder the same plan lays.  Every row is executed,
        because a plan that the emitter accepts is still not evidence that
        the program computes the table.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run
        from esolangs.tools import parameterized
        from tests.tools.fills import _fill_pct_squared_minus_one

        n = 10
        table = "".join(
            str(((r >> (n - 1)) & 1) ^ ((r >> (n - 2)) & 1)) for r in range(2**n)
        )
        template = parameterized.pct_squared_minus_one(table)
        widths = set()
        for row in range(2**n):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            program = _fill_pct_squared_minus_one(template, bits)
            widths.add(len(program))
            io = ScriptedIO()
            run(program, io)
            assert io.getvalue() == table[row], f"row {row}"
        assert len(widths) == 1, widths

    @pytest.mark.slow  # ~14s: eleven inputs, a sampled row sweep
    def test_the_packed_ladder_reaches_eleven_inputs(self) -> None:
        """Eleven inputs build on the packed ladder and print correctly.

        The uniform ladders both overrun the workspace here -- 8188 and 4094
        against 3003 -- so this arity exists only because the packed ladder
        spends ``2**n + 1``.  Rows are *sampled* rather than swept: all 2048
        take about two minutes on the interpreter, well past this module's
        budget, and the full sweep is a notes probe instead.
        """
        import random

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run
        from esolangs.tools import parameterized
        from tests.tools.fills import _fill_pct_squared_minus_one

        n = 11
        rng = random.Random(11011)
        table = "".join(rng.choice("01") for _ in range(2**n))
        template = parameterized.pct_squared_minus_one(table)
        widths = set()
        for row in range(0, 2**n, 97):  # a stride coprime to the arity's runs
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            program = _fill_pct_squared_minus_one(template, bits)
            widths.add(len(program))
            io = ScriptedIO()
            run(program, io)
            assert io.getvalue() == table[row], f"row {row}"
        assert len(widths) == 1, widths

    @pytest.mark.slow  # generic twelve-input fold: ~12s to plan
    def test_interleaved_fold_builds_a_generic_twelve_input_table(self) -> None:
        """A centred final embed escapes the all-row ladder's limit."""
        import random

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run
        from esolangs.tools import parameterized
        from tests.tools.fills import _fill_pct_squared_minus_one

        rng = random.Random(1)
        table = "".join(rng.choice("01") for _ in range(2**12))
        template = parameterized.pct_squared_minus_one(table)
        widths = set()
        for row in range(0, 2**12, 97):
            bits = [(row >> shift) & 1 for shift in range(11, -1, -1)]
            program = _fill_pct_squared_minus_one(template, bits)
            widths.add(len(program))
            io = ScriptedIO()
            run(program, io)
            assert io.getvalue() == table[row], row
        assert len(widths) == 1, widths

    @pytest.mark.slow  # packed prefix + sixteen-class compaction: ~69s to plan
    @pytest.mark.weekly
    def test_interleaved_fold_builds_a_generic_thirteen_input_table(self) -> None:
        """The packed prefix ladder compacts to its cofactors before laying.

        Thirteen inputs need the eleven-input packed ladder, whose unit gaps
        jam the conveyor; the pre-lay compaction to at most sixteen cofactor
        points, and the collision-free split total, are what this exercises.

        69.1s, second-most expensive in the suite, so it runs weekly rather
        than on every ``test-full``; see the ``weekly`` marker.  It is the
        executable witness for the thirteen-input reach that `walls.md` and
        `limitations.md` both claim, so it is deferred, never dropped.
        """
        import random

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run
        from esolangs.tools import parameterized
        from tests.tools.fills import _fill_pct_squared_minus_one

        rng = random.Random(13)
        table = "".join(rng.choice("01") for _ in range(2**13))
        template = parameterized.pct_squared_minus_one(table)
        widths = set()
        for row in range(0, 2**13, 331):
            bits = [(row >> shift) & 1 for shift in range(12, -1, -1)]
            program = _fill_pct_squared_minus_one(template, bits)
            widths.add(len(program))
            io = ScriptedIO()
            run(program, io)
            assert io.getvalue() == table[row], row
        assert len(widths) == 1, widths

    @pytest.mark.slow  # ~10s to build, then sampled rows at ~0.6s each
    def test_the_staged_fold_builds_the_dense_fourteen_input_fixture(self) -> None:
        """Fourteen inputs: the stage lays when the lay fits, carrying pairs.

        The dense fixture is the table the pair route refused -- its
        eleven-input cut has 256 classes, and compacting to them strands
        four pairs the conveyor cycles on forever.  Laid at the first
        checkpoint where a split fits (725 points), the carried pairs
        merge in the sixteen-class stage.  Measured: 289k moves, 1.6 MB,
        ~10 s; twelve sampled rows print on the interpreter.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.pct_squared_minus_one import run
        from esolangs.tools import parameterized
        from tests.tools.fills import _fill_pct_squared_minus_one
        from tests.tools.test_boolean_contract import _dense

        n = 14
        table = _dense(n)
        template = parameterized.pct_squared_minus_one(table)
        assert len(template) < 2_500_000
        widths = set()
        for row in range(0, 2**n, 1381):
            bits = [(row >> shift) & 1 for shift in range(n - 1, -1, -1)]
            program = _fill_pct_squared_minus_one(template, bits)
            widths.add(len(program))
            io = ScriptedIO()
            run(program, io)
            assert io.getvalue() == table[row], row
        assert len(widths) == 1, widths

    @pytest.mark.slow  # ~10s: 450k rule moves before the stall is evident
    def test_compacting_straight_to_the_fourteen_input_classes_stalls(self) -> None:
        """The clean two-stage build (ladder, then compact to 256, then a
        tiny tail ladder) is not reachable: the compaction step alone
        cannot finish.

        Laying the eleven-input packed ladder and grouping by the
        remaining three inputs' cofactor gives 2048 points in exactly 256
        classes -- the same numbers :func:`_interleaved_final_pair`'s
        docstring reports.  Feeding that state straight to
        :func:`_fold_reduce` (the same conveyor :func:`_staged_fold` uses
        per lay, unbounded here) merges down to 260 points in 413,978
        moves and 33.4M relocations, then cycles for the rest of a
        450,000-move budget -- almost entirely ``d`` (bottom) wipes with
        an occasional ``m`` doubling to regrow the window, no ``u`` wipe
        and no merge -- and returns ``None``.  The failing move is
        :meth:`_FoldLedger.rule_move`'s case 2 (dive onto the nearest
        same-class wiped point): for the four stranded pairs, no landing
        in ``[ref + _LIMIT + 1, ref + _LIMIT + q1]`` ever coincides with
        the partner's position, at any window the doublings reach --
        "case 2's window only ever serves its own class" (comment above
        :data:`_FOLD_STEP_SLOPE`).  This is why :func:`_staged_fold` lays
        the twelfth through fourteenth inputs incrementally instead of
        compacting once up front.
        """
        from esolangs.tools import pct_fold as module
        from esolangs.tools.pct_fold_plan import (
            _cofactor_done,
            _fold_norm,
            _fold_reduce,
        )
        from tests.tools.test_boolean_contract import _dense

        n, prefix = 14, 11
        table = _dense(n)
        weights = module._fold_subset_weights(prefix)  # noqa: SLF001
        positions = module._fold_positions(prefix, weights)  # noqa: SLF001
        block = 2 ** (n - prefix)
        state = _fold_norm(
            [
                (
                    positions[row],
                    0,
                    table[row * block : (row + 1) * block],
                    frozenset(range(row * block, (row + 1) * block)),
                )
                for row in range(2**prefix)
            ]
        )
        assert len(state) == 2048
        assert len({c for _, _, c, _ in state}) == 256
        assert _fold_reduce(state, _cofactor_done, budget=450_000) is None

    @pytest.mark.slow  # ~1s: the stall guard on 2048 unmergeable points
    def test_the_dense_fifteen_input_fixture_is_refused_by_name(self) -> None:
        """Fifteen inputs: the eleven-input cut does not compact, so refuse.

        2017 distinct sixteen-row cofactors among 2048 rows leave nothing
        to merge before the lay, and the laid points jam the window; the
        refusal says so rather than emitting a partial program.
        """
        from esolangs.exceptions import GeneratorCapError
        from esolangs.tools import parameterized
        from tests.tools.test_boolean_contract import _dense

        with pytest.raises(GeneratorCapError, match="2017 distinct"):
            parameterized.pct_squared_minus_one(_dense(15))

    def test_a_table_whose_plan_fails_builds_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No plan means no template, not a partial one.

        Every table tried plans successfully -- the fold is documented as
        found in practice rather than proved total -- so the refusal is
        driven by making the planner decline instead of hunting for a
        table that defeats it.  The table used here builds normally when
        the planner is left alone.
        """
        module = self.module()
        assert module._fold("0011", 2) is not None  # noqa: SLF001

        monkeypatch.setattr(module, "_fold_plan", lambda *_a, **_k: None)
        assert module._fold("0011", 2) is None  # noqa: SLF001


class TestPctFoldSkeletonResolver:
    """The tabulated planner's refusals, driven on constructed states.

    ``_fold_construct`` builds a plan with :func:`_fold_skeleton` and
    resolves each symbolic amount against the live state, so every refusal
    is a property of the *geometry* rather than of a table.  Building the
    states directly is what reaches them: a wipe that leaves no survivor and
    a landing that does not match are both shapes the fold's own planner
    steers around, so no generated table drives one.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.pct_squared_minus_one")

    #: One point: whichever way it is wiped, nothing survives.
    LONE = ((0, 0, "a", frozenset({0})),)

    #: Two points of one class, four apart and both already wiped.
    PAIR = (
        (0, 0, "a", frozenset({0})),
        (-4, 0, "a", frozenset({1})),
    )

    @pytest.mark.parametrize("kind", ["d", "u"])
    def test_geometry_refuses_a_wipe_that_leaves_no_survivor(self, kind: str) -> None:
        """Both branches measure the window against the survivors."""
        module = self.module()
        assert module._fold_geometry(self.LONE, kind, 1) is None  # noqa: SLF001

    def test_resolve_passes_on_a_wipe_with_no_geometry(self) -> None:
        """A symbolic amount cannot be resolved where the window does not exist."""
        module = self.module()
        assert module._fold_resolve(self.LONE, "d", 1, "cmax") is None  # noqa: SLF001

    def test_resolve_refuses_a_landing_index_past_the_survivors(self) -> None:
        """``landN`` names a survivor by index, and one wipe leaves only one."""
        module = self.module()
        assert module._fold_resolve(self.PAIR, "d", 1, "land9") is None  # noqa: SLF001

    def test_resolve_refuses_a_landing_that_does_not_match(self) -> None:
        """A landing is a merge, so span, class and window all have to agree."""
        module = self.module()
        assert module._fold_resolve(self.PAIR, "d", 1, "land0") is None  # noqa: SLF001

    def test_construct_emits_an_empty_plan_for_a_finished_state(self) -> None:
        """Two wiped points of different classes is what ``_fold_done`` accepts."""
        module = self.module()
        finished = (
            (0, 0, "a", frozenset({0})),
            (-5, 0, "b", frozenset({1})),
        )
        assert module._fold_construct(finished) == []  # noqa: SLF001
