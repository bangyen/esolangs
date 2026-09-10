"""Minifuck chain paths the generator's own budgets never reach."""

import importlib

import pytest

from esolangs.tools.boolean.minifuck import _BASE, _CHAIN_CAP, _Chain


class TestChainExtent:
    """``extent`` inverts the staircase, clamped to the chain's ceiling."""

    def test_a_budget_past_the_chain_is_clamped_to_the_ceiling(self) -> None:
        """No budget buys more cells than the chain holds."""
        chain = _Chain([0] * _CHAIN_CAP)
        assert chain.extent(10**6) == (_CHAIN_CAP - 3, False)

    def test_the_clamp_is_the_same_for_a_chain_of_ones(self) -> None:
        # Crossing costs two instructions per cell here rather than one,
        # so the ceiling is reached by a different route to the same cap.
        chain = _Chain([1] * _CHAIN_CAP)
        extent, _ = chain.extent(10**6)
        assert extent == _CHAIN_CAP - 3

    def test_a_budget_inside_the_chain_is_not_clamped(self) -> None:
        chain = _Chain([0] * _CHAIN_CAP)
        extent, _ = chain.extent(_BASE + 2)
        assert extent < _CHAIN_CAP - 3


class TestStagingIndexBudget:
    """The index stops mid-pass when its accumulator budget runs out.

    ``_budget`` returns None at every shipped arity, so the exit is dead
    as configured; a budget landing inside the insert pass is what shows
    it stops rather than running the enumeration out.
    """

    def test_a_smaller_budget_indexes_strictly_fewer_columns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each exit truncates the enumeration where the budget ran out.

        Three budgets, three prefixes of the same order: 200 stops in the
        bracket pass, 7600 inside the insert pass, 20000 later still.  The
        counts must grow with the budget, and each smaller index must be a
        sub-map of the larger -- a prefix, not a different walk.
        """
        module = importlib.import_module("esolangs.tools.boolean.minifuck")
        indexes = []
        for budget in (200, 7600, 20_000):
            module._staging_index.cache_clear()  # noqa: SLF001
            with monkeypatch.context() as patch:
                patch.setattr(module, "_budget", lambda _n, b=budget: b)
                indexes.append(module._staging_index(4))  # noqa: SLF001
        module._staging_index.cache_clear()  # noqa: SLF001

        small, middle, large = indexes
        assert len(small) < len(middle) < len(large)
        assert all(middle[key] == value for key, value in small.items())
        assert all(large[key] == value for key, value in middle.items())
