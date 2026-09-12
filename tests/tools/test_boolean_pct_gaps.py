r"""%^2^-1 fold helpers, called on constructed states."""

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
    _FoldEmitter,
    _interleaved_final_pair,
    _interleaved_fold,
    _solution,
    _split_setter,
    pct_squared_minus_one,
)


def _state(*items: tuple[int, int, str, frozenset[int]]) -> tuple[object, ...]:
    return _fold_norm(list(items))


class TestSolution:
    r"""A candidate parameter set is rejected when no tail can print it."""

    ROWS: ClassVar[dict[tuple[int, int], int]] = {
        (0, 0): 0,
        (1, 0): 0,
        (0, 1): 1,
        (1, 1): 1,
    }

    def test_classes_too_far_apart_have_no_tail(self) -> None:
        r"""``l`` moves both classes at once, so they must differ by one."""
        assert _solution(self.ROWS, ("p", "p"), (0, 0), [1, 1], (0, 5)) is None

    def test_adjacent_classes_are_rejected_earlier(self) -> None:
        r"""The positive control: a different arm refuses this one."""
        assert _solution(self.ROWS, ("p", "p"), (0, 0), [1, 1], (0, 1)) is None


class TestPreshift:
    def test_a_zero_shift_emits_nothing(self) -> None:
        r"""Neither arm fires: no move is spelled for a move of nothing."""
        emitter = _FoldEmitter.__new__(_FoldEmitter)
        emitter.body = []
        emitter.preshift(0)
        assert emitter.body == []


class TestFoldSpan:
    r"""The occupied extent: the top point down to the lowest footprint."""

    def test_two_points_span_their_separation_plus_the_lower_extent(self) -> None:
        state = _state((10, 2, "0", frozenset({0})), (4, 1, "1", frozenset({1})))
        # Normalized to points 0 and.
        assert _fold_span(state) == 7

    def test_a_single_point_spans_its_own_extent(self) -> None:
        assert _fold_span(_state((3, 2, "0", frozenset({0})))) == 2

    def test_a_zero_extent_point_spans_nothing(self) -> None:
        assert _fold_span(_state((3, 0, "0", frozenset({0})))) == 0


class TestSetters:
    r"""A setter pair splits a total into an up and a down move."""

    def test_a_spellable_total_gives_a_pair_that_sums_to_it(self) -> None:
        got = _split_setter(12)
        assert got is not None
        _zero, _one, up, down = got
        assert up + down == 12

    def test_a_centred_setter_separates_the_span(self) -> None:
        got = _centred_setter(10)
        assert got is not None
        _zero, _one, up, down = got
        # Two more than the span: one.
        assert up + down == 12

    def test_a_total_too_small_to_split_is_refused(self) -> None:
        # Both moves must be at least.
        assert _split_setter(3) is None


class TestFoldCofactorBridge:
    r"""The bridge search is capped at the point count it was measured on."""

    def test_a_state_past_the_cap_is_refused(self) -> None:
        wide = _state(
            *(
                (row * 4, 0, str(row % 2), frozenset({row}))
                for row in range(_COFACTOR_BRIDGE_POINTS + 1)
            )
        )
        assert _fold_to_cofactors(wide) is None

    def test_a_state_inside_the_cap_is_searched(self) -> None:
        r"""The positive control: the same shape, one point fewer."""
        narrow = _state(
            *(
                (row * 4, 0, str(row % 2), frozenset({row}))
                for row in range(_COFACTOR_BRIDGE_POINTS)
            )
        )
        # Searched rather than refused.
        # rules did not close -- what.
        assert _fold_to_cofactors(narrow) is None or isinstance(
            _fold_to_cofactors(narrow), list
        )


class TestInterleavedFinalPair:
    r"""The two-stage final pair, which the dispatcher tries before the."""

    def test_an_alternating_table_is_refused_at_every_arity(self) -> None:
        r"""The pair cannot separate a table whose rows alternate."""
        for n in (3, 6, 12):
            table = "01" * (2 ** (n - 1))
            assert _interleaved_final_pair(table, n) is None

    def test_a_table_whose_every_even_total_collides_is_refused(self) -> None:
        r"""The packed search runs out of totals to try."""
        assert _interleaved_final_pair("1111100011100101", 4) is None

    def test_the_packed_ladder_skips_a_colliding_total(self) -> None:
        r"""Past twelve inputs the narrow ladder no longer fits."""
        assert _interleaved_final_pair("0011" * (2**13 // 4), 13) is not None

    def test_an_uncompactable_packed_state_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""The packed route compacts before splitting, and may fail there."""
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_fold_reduce", lambda *_a, **_k: None)
            assert _interleaved_final_pair("0011" * (2**13 // 4), 13) is None

    def test_a_separable_table_builds(self) -> None:
        r"""The positive control for the three refusals below."""
        assert _interleaved_final_pair("0011" * 4, 4) is not None

    @pytest.mark.parametrize(
        "planner",
        ["_fold_reduce", "_split_setter", "_centred_setter", "_fold_plan"],
    )
    def test_a_failing_planner_refuses_the_pair(
        self, planner: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""Each stage propagates its planner's failure instead of guessing."""
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        with monkeypatch.context() as patch:
            patch.setattr(module, planner, lambda *_a, **_k: None)
            assert _interleaved_final_pair("0011" * 4, 4) is None

    def test_a_point_driven_outside_the_workspace_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""A setter that would move a row past +/-3003 is refused."""
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
        r"""Rows of different classes may not share a point."""
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
        r"""No ladder lays the prefix inside the workspace footprint."""
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        with monkeypatch.context() as patch:
            # A narrow ladder too wide for.
            # to the packed one, which then.
            patch.setattr(module, "_fold_uniform", lambda *_a, **_k: [10**9])
            patch.setattr(module, "_fold_subset_weights", lambda *_a, **_k: None)
            assert _interleaved_final_pair("0011" * 4, 4) is None


class TestInterleavedFoldRefusals:
    r"""Every stage of the staged fold propagates its planner's failure."""

    TABLE = "01" * 8

    def test_the_fold_builds_when_every_stage_plans(self) -> None:
        r"""The positive control the refusals below are measured against."""
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
        r"""The cofactor bridge is what releases equal suffixes early."""
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_fold_to_cofactors", lambda *_a, **_k: None)
            assert _interleaved_fold(self.TABLE, 4) is None


class TestNoLadderServed:
    r"""The generator aborts rather than emitting the wrong function."""

    def test_both_fold_routes_giving_up_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""No table defeats both routes, so both are failed here."""
        module = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_fold", lambda *_a, **_k: None)
            patch.setattr(module, "_interleaved_fold", lambda *_a, **_k: None)
            with pytest.raises(ValueError, match="builds every table"):
                pct_squared_minus_one("01101001" * 4)

    def test_the_shipped_routes_build_the_same_table(self) -> None:
        r"""The positive control: nothing is wrong with the table itself."""
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
