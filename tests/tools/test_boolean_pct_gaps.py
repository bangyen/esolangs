"""%^2^-1 fold helpers, called on constructed states.

The fold's planner reaches these only at the arities where a staged
prefix is laid, and building such a table through the public generator
costs minutes per row.  The states are the shapes ``_fold_norm``
produces, so each helper is asked the question it answers in the plan.
"""

import importlib
from typing import ClassVar

import pytest

from esolangs.tools.boolean.pct_squared_minus_one import (
    _COFACTOR_BRIDGE_POINTS,
    _centred_setter,
    _cofactor_done,
    _fold_norm,
    _fold_span,
    _fold_to_cofactors,
    _interleaved_final_pair,
    _interleaved_fold,
    _solution,
    _split_setter,
    pct_squared_minus_one,
)


def _state(*items: tuple[int, int, str, frozenset[int]]) -> tuple[object, ...]:
    return _fold_norm(list(items))


class TestSolution:
    """A candidate parameter set is rejected when no tail can print it."""

    ROWS: ClassVar[dict[tuple[int, int], int]] = {
        (0, 0): 0,
        (1, 0): 0,
        (0, 1): 1,
        (1, 1): 1,
    }

    def test_classes_too_far_apart_have_no_tail(self) -> None:
        """``l`` moves both classes at once, so they must differ by one."""
        assert _solution(self.ROWS, ("p", "p"), (0, 0), [1, 1], (0, 5)) is None

    def test_adjacent_classes_are_rejected_earlier(self) -> None:
        """The positive control: a different arm refuses this one.

        Classes one apart *do* have a tail, so reaching None here means
        the padding rejected the pair -- not the tail check above.
        """
        assert _solution(self.ROWS, ("p", "p"), (0, 0), [1, 1], (0, 1)) is None


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
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
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
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
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
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
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
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
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
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
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
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_fold_plan", lambda *_a, **_k: None)
            assert _interleaved_fold(self.TABLE, 4) is None

    def test_an_unbridgeable_cofactor_stage_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The cofactor bridge is what releases equal suffixes early."""
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
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
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
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
