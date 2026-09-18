"""%^2^-1 fold helpers, called on constructed states.

The fold's planner reaches these only at the arities where a staged
prefix is laid, and building such a table through the public generator
costs minutes per row.  The states are the shapes ``_fold_norm``
produces, so each helper is asked the question it answers in the plan.
"""

import importlib

import pytest

from esolangs.tools.pct_squared_minus_one import (
    _COFACTOR_BRIDGE_POINTS,
    _centred_setter,
    _cofactor_done,
    _fold_norm,
    _fold_to_cofactors,
    _FoldEmitter,
    _interleaved_final_pair,
    _interleaved_fold,
    _split_setter,
    pct_squared_minus_one,
)
from tests.tools.pct_support import _fold_span


def _state(*items: tuple[int, int, str, frozenset[int]]) -> tuple[object, ...]:
    return _fold_norm(list(items))


class TestPreshift:
    def test_a_zero_shift_emits_nothing(self) -> None:
        """Neither arm fires: no move is spelled for a move of nothing.

        Every shipped caller computes a nonzero delta, so this is the one
        place the no-op is exercised.
        """
        emitter = _FoldEmitter.__new__(_FoldEmitter)
        emitter.body = []
        emitter.preshift(0)
        assert emitter.body == []


class TestFoldSpan:
    """The occupied extent: the top point down to the lowest footprint."""

    def test_two_points_span_their_separation_plus_the_lower_extent(self) -> None:
        state = _state((10, 2, "0", frozenset({0})), (4, 1, "1", frozenset({1})))
        # Normalized to points 0 and -6; the lower one reaches one further.
        assert _fold_span(state) == 7

    def test_a_single_point_spans_its_own_extent(self) -> None:
        assert _fold_span(_state((3, 2, "0", frozenset({0})))) == 2

    def test_a_zero_extent_point_spans_nothing(self) -> None:
        assert _fold_span(_state((3, 0, "0", frozenset({0})))) == 0


class TestSetters:
    """A setter pair splits a total into an up and a down move."""

    def test_a_spellable_total_gives_a_pair_that_sums_to_it(self) -> None:
        got = _split_setter(12)
        assert got is not None
        _zero, _one, up, down = got
        assert up + down == 12

    def test_a_centred_setter_separates_the_span(self) -> None:
        got = _centred_setter(10)
        assert got is not None
        _zero, _one, up, down = got
        # Two more than the span: one clear cell on each side.
        assert up + down == 12

    def test_a_total_too_small_to_split_is_refused(self) -> None:
        # Both moves must be at least 2, so 3 cannot be spelled.
        assert _split_setter(3) is None


class TestFoldCofactorBridge:
    """The bridge search is capped at the point count it was measured on."""

    def test_a_state_past_the_cap_is_refused(self) -> None:
        wide = _state(
            *(
                (row * 4, 0, str(row % 2), frozenset({row}))
                for row in range(_COFACTOR_BRIDGE_POINTS + 1)
            )
        )
        assert _fold_to_cofactors(wide) is None

    def test_a_state_inside_the_cap_is_searched(self) -> None:
        """The positive control: the same shape, one point fewer."""
        narrow = _state(
            *(
                (row * 4, 0, str(row % 2), frozenset({row}))
                for row in range(_COFACTOR_BRIDGE_POINTS)
            )
        )
        # Searched rather than refused outright: a list, or None if the
        # rules did not close -- what must not happen is the cap firing.
        assert _fold_to_cofactors(narrow) is None or isinstance(
            _fold_to_cofactors(narrow), list
        )


class TestInterleavedFinalPair:
    """The two-stage final pair, which the dispatcher tries before the fold."""

    def test_an_alternating_table_is_refused_at_every_arity(self) -> None:
        """The pair cannot separate a table whose rows alternate.

        Its setter search walks the distances between points and finds no
        collision-free total, so it declines rather than mis-separating.
        """
        for n in (3, 6, 12):
            table = "01" * (2 ** (n - 1))
            assert _interleaved_final_pair(table, n) is None

    def test_a_table_whose_every_even_total_collides_is_refused(self) -> None:
        """The packed search runs out of totals to try.

        Found by sweeping random four-input tables: this one's points sit
        at every even distance the loop walks, so no split is free.
        """
        assert _interleaved_final_pair("1111100011100101", 4) is None

    def test_the_packed_ladder_skips_a_colliding_total(self) -> None:
        """Past twelve inputs the narrow ladder no longer fits.

        The packed ladder's own setter search walks even totals and steps
        over any that is already a distance between two points.
        """
        assert _interleaved_final_pair("0011" * (2**13 // 4), 13) is not None

    def test_an_uncompactable_packed_state_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The packed route compacts before splitting, and may fail there.

        Only the packed ladder compacts, so this needs the thirteen-input
        route; the first reduce is the compaction, and failing it is what
        the guard answers.
        """
        module = importlib.import_module("esolangs.tools.pct_fold")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_fold_reduce", lambda *_a, **_k: None)
            assert _interleaved_final_pair("0011" * (2**13 // 4), 13) is None

    def test_a_separable_table_builds(self) -> None:
        """The positive control for the three refusals below."""
        assert _interleaved_final_pair("0011" * 4, 4) is not None

    @pytest.mark.parametrize(
        "planner",
        ["_fold_reduce", "_split_setter", "_centred_setter", "_fold_plan"],
    )
    def test_a_failing_planner_refuses_the_pair(
        self, planner: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each stage propagates its planner's failure instead of guessing.

        The same table builds when every planner answers (above), so the
        None here is the guard firing rather than the table being hard.
        """
        module = importlib.import_module("esolangs.tools.pct_fold")
        with monkeypatch.context() as patch:
            patch.setattr(module, planner, lambda *_a, **_k: None)
            assert _interleaved_final_pair("0011" * 4, 4) is None

    def test_a_point_driven_outside_the_workspace_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A setter that would move a row past +/-3003 is refused.

        ``_apply`` runs in the setter and emit passes too, so replacing it
        outright fails before the layout starts; the 21st call is the
        first one inside the row loop, and poisoning that one lands the
        point outside the workspace.
        """
        module = importlib.import_module("esolangs.tools.pct_fold")
        original = module._apply  # noqa: SLF001
        calls = [0]

        def past_the_limit(value: int, code: str) -> int:
            calls[0] += 1
            return 10**9 if calls[0] > 20 else original(value, code)

        with monkeypatch.context() as patch:
            patch.setattr(module, "_apply", past_the_limit)
            assert _interleaved_final_pair("0011" * 4, 4) is None

    def test_two_classes_landing_on_one_point_refuse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rows of different classes may not share a point.

        Same poisoned call as above, but landing every later row on the
        same value: the second one to arrive carries a different class and
        the collision check refuses it.
        """
        module = importlib.import_module("esolangs.tools.pct_fold")
        original = module._apply  # noqa: SLF001
        calls = [0]

        def onto_one_point(value: int, code: str) -> int:
            calls[0] += 1
            return 0 if calls[0] > 20 else original(value, code)

        with monkeypatch.context() as patch:
            patch.setattr(module, "_apply", onto_one_point)
            assert _interleaved_final_pair("0011" * 4, 4) is None

    def test_an_unspellable_prefix_ladder_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No ladder lays the prefix inside the workspace footprint."""
        module = importlib.import_module("esolangs.tools.pct_fold")
        with monkeypatch.context() as patch:
            # A narrow ladder too wide for the workspace sends the choice
            # to the packed one, which then declines.
            patch.setattr(module, "_fold_uniform", lambda *_a, **_k: [10**9])
            patch.setattr(module, "_fold_subset_weights", lambda *_a, **_k: None)
            assert _interleaved_final_pair("0011" * 4, 4) is None


class TestInterleavedFoldRefusals:
    """Every stage of the staged fold propagates its planner's failure.

    The guards exist so a stage that cannot be planned aborts the whole
    build rather than emitting a program for the wrong function.  Each is
    reached by failing one sub-planner, since no table the generator
    ships defeats them.
    """

    TABLE = "01" * 8

    def test_the_fold_builds_when_every_stage_plans(self) -> None:
        """The positive control the refusals below are measured against."""
        assert _interleaved_fold(self.TABLE, 4) is not None

    def test_an_unplannable_final_stage_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = importlib.import_module("esolangs.tools.pct_fold")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_fold_plan", lambda *_a, **_k: None)
            assert _interleaved_fold(self.TABLE, 4) is None

    def test_an_unbridgeable_cofactor_stage_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The cofactor bridge is what releases equal suffixes early."""
        module = importlib.import_module("esolangs.tools.pct_fold")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_fold_to_cofactors", lambda *_a, **_k: None)
            assert _interleaved_fold(self.TABLE, 4) is None


class TestNoLadderServed:
    """The generator aborts rather than emitting the wrong function."""

    def test_both_fold_routes_giving_up_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No table defeats both routes, so both are failed here.

        Emitting nothing beats emitting a program for another function,
        which is what this last-resort guard is for.
        """
        module = importlib.import_module("esolangs.tools.pct_squared_minus_one")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_fold", lambda *_a, **_k: None)
            patch.setattr(module, "_interleaved_fold", lambda *_a, **_k: None)
            with pytest.raises(ValueError, match="builds every table"):
                pct_squared_minus_one("01101001" * 4)

    def test_the_shipped_routes_build_the_same_table(self) -> None:
        """The positive control: nothing is wrong with the table itself."""
        assert pct_squared_minus_one("01101001" * 4)


class TestCofactorDone:
    def test_one_point_per_class_is_done(self) -> None:
        state = _state((4, 0, "0", frozenset({0})), (0, 0, "1", frozenset({1})))
        assert _cofactor_done(state) is True

    def test_two_points_sharing_a_class_are_not_done(self) -> None:
        state = _state(
            (8, 0, "0", frozenset({0})),
            (4, 0, "0", frozenset({1})),
            (0, 0, "1", frozenset({2})),
        )
        assert _cofactor_done(state) is False


class TestStagedFold:
    """The fourteen-input route, driven at small arities through ``prefix``.

    ``_staged_fold`` lays one input per stage as soon as a collision-free
    split fits the window and the rules run on the laid state; nothing in
    it depends on the arity except the packed ladder's width, so the
    stages are exercised on four- to six-input tables and the fourteen-
    input build is the slow witness in ``test_boolean_pct_fold``.
    """

    @staticmethod
    def module():
        return importlib.import_module("esolangs.tools.pct_fold")

    @staticmethod
    def dense(n: int) -> str:
        from tests.tools.test_boolean_contract import _dense

        return _dense(n)

    @pytest.mark.parametrize(("n", "prefix"), [(3, 11), (4, 11), (5, 11), (5, 3)])
    def test_every_row_prints_through_the_stages(self, n: int, prefix: int) -> None:
        """A dense table laid one input per stage executes on every row.

        The prefix clamps to ``n - 1``, one lay; ``(5, 3)`` is two stages,
        the first probed by the rules and the second by the planner.
        """
        from tests.tools.test_boolean_pct import _executes

        table = self.dense(n)
        template = self.module()._staged_fold(table, n, prefix)  # noqa: SLF001
        assert template is not None
        _executes(template, table, n)

    def test_the_lay_waits_for_a_checkpoint_where_it_fits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Checked every merge, a stage lays as soon as the split fits.

        Small ladders fit at once, so the first fit test is refused by hand
        and the stage has to run the rules to its next checkpoint.
        """
        from tests.tools.test_boolean_pct import _executes

        module = self.module()
        real = module._staged_lay_total  # noqa: SLF001
        asked: list[int] = []

        def first_refused(tops: list[int]) -> int | None:
            asked.append(len(tops))
            return None if len(asked) == 1 else real(tops)

        monkeypatch.setattr(module, "_STAGED_CHECK", 1)
        monkeypatch.setattr(module, "_staged_lay_total", first_refused)
        table = self.dense(5)
        template = module._staged_fold(table, 5, prefix=4)  # noqa: SLF001
        assert template is not None
        assert asked[1] < asked[0]  # laid at the checkpoint after a merge
        _executes(template, table, 5)

    def test_past_thirteen_the_interleaved_fold_dispatches_to_the_stages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fourteen inputs never reach the all-row path below the pair."""
        module = self.module()
        monkeypatch.setattr(module, "_staged_fold", lambda *_a, **_k: "staged")
        assert _interleaved_fold("0" * 2**14, 14) == "staged"

    def test_a_compact_state_the_lay_never_fits_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Compacted to one point per class and still no split: refused."""
        module = self.module()
        monkeypatch.setattr(module, "_staged_lay_total", lambda *_a: None)
        assert module._staged_fold(self.dense(4), 4) is None  # noqa: SLF001

    def test_a_dead_conveyor_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No rule move before the lay fits: refused, not guessed."""
        module = self.module()
        monkeypatch.setattr(module, "_staged_lay_total", lambda *_a: None)
        monkeypatch.setattr(module._FoldLedger, "rule_move", lambda _s: None)  # noqa: SLF001
        assert module._staged_fold(self.dense(4), 4) is None  # noqa: SLF001

    def test_a_stalled_conveyor_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Moves without a merge past the stall bound are the fifteen-input
        obstruction in miniature: the stage is abandoned."""
        module = self.module()
        monkeypatch.setattr(module, "_STAGED_STALL", 0)
        monkeypatch.setattr(module, "_staged_lay_total", lambda *_a: None)
        assert module._staged_fold(self.dense(5), 5) is None  # noqa: SLF001

    def test_a_last_lay_without_a_plan_is_not_taken(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The final lay is probed with the endgame planner before it is spelled."""
        module = self.module()
        monkeypatch.setattr(module, "_fold_plan", lambda *_a: None)
        assert module._staged_fold(self.dense(4), 4) is None  # noqa: SLF001

    def test_a_lay_the_rules_cannot_run_is_not_taken(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A split that fits but jams the conveyor waits for the next checkpoint."""
        module = self.module()
        monkeypatch.setattr(module, "_staged_runs", lambda _l: False)
        assert module._staged_fold(self.dense(5), 5, prefix=3) is None  # noqa: SLF001

    def test_the_probe_reports_a_dead_or_stalled_laid_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = self.module()
        ledger = module._FoldLedger.from_state(  # noqa: SLF001
            _state(
                (0, 0, "a", frozenset({0})),
                (-3, 0, "b", frozenset({1})),
                (-6, 0, "a", frozenset({2})),
            )
        )
        with monkeypatch.context() as patch:
            patch.setattr(module._FoldLedger, "rule_move", lambda _s: None)  # noqa: SLF001
            assert module._staged_runs(ledger) is False  # noqa: SLF001
        with monkeypatch.context() as patch:
            patch.setattr(module, "_STAGED_STALL", 0)
            patch.setattr(
                module._FoldLedger,  # noqa: SLF001
                "rule_move",
                lambda _s: ("m", 0, 0, frozenset()),
            )
            assert module._staged_runs(ledger) is False  # noqa: SLF001

    def test_the_probe_accepts_a_state_that_is_already_compact(self) -> None:
        module = self.module()
        ledger = module._FoldLedger.from_state(  # noqa: SLF001
            _state((0, 0, "a", frozenset({0})), (-4, 0, "b", frozenset({1})))
        )
        assert module._staged_runs(ledger) is True  # noqa: SLF001

    @pytest.mark.parametrize(
        ("tops", "total"),
        [
            ([0, 6003], None),  # no room under the window for any split
            ([0, 3], 4),  # the first even total, three is not a distance
            ([0, 4], 6),  # four is a distance, so the next even total
            ([0, 1, 5000], 4),  # the distance walk stops past the room left
            ([*range(0, 18, 2), 5990], None),  # room 16: every total collides
        ],
    )
    def test_the_split_total_skips_every_distance(
        self, tops: list[int], total: int | None
    ) -> None:
        assert self.module()._staged_lay_total(tops) == total  # noqa: SLF001
