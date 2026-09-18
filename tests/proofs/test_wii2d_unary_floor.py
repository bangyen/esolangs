"""WII2D's first fold pays its midpoint in unary (see ``test_negatives.py``).

On the LFSR witness every legal first fold merging 3+ values costs
``scale + |centre| + 1`` of 59 at domain 32 and 121 at 64, and no centre
within 8 of the origin merges more than 2: the optima's near-origin first
epoch cannot open this family.  The shipped decoder's own first fold pays
exactly the floor, so no first-fold rule -- ranked or named -- beats it here.
First step only; lifting it to every epoch is the open half of the bound.
"""

import pytest

from esolangs.tools.wii2d import (
    _wii2d_decode,
    _wii2d_folds,
    _wii2d_points,
)


def _lfsr(domain: int) -> list[int]:
    """Return the first ``domain`` bits of a 5-bit maximal LFSR."""
    state = 1
    result: list[int] = []
    for _ in range(domain):
        result.append(state & 1)
        state = ((state >> 1) ^ (-(state & 1) & 18)) & 31
    return result


def _first_epoch_costs(domain: int) -> dict[int, tuple[int, int, int]]:
    """Map merges to ``(cost, scale, centre)`` of the cheapest legal first fold.

    Exhaustive over scales 0/1 and every same-bit midpoint from the decode
    start (values ``0 .. domain - 1``); cost is the unary spelling.
    """
    pattern = _lfsr(domain)
    best: dict[int, tuple[int, int, int]] = {}
    for scale in (0, 1):
        scaled = [value * 2 if scale else value for value in range(domain)]
        live = _wii2d_points(scaled, pattern)
        assert live is not None
        points = sorted(live)
        zeros = [point for point in points if live[point] == 0]
        ones = [point for point in points if live[point] == 1]
        crossing = {zero + one for zero in zeros for one in ones}
        merging: dict[int, int] = {}
        for group in (zeros, ones):
            for index, first in enumerate(group):
                for second in group[index + 1 :]:
                    if (first + second) % 2 == 0 and first + second not in crossing:
                        merging[first + second] = merging.get(first + second, 0) + 1
        for double, merges in merging.items():
            cost = scale + abs(double // 2) + 1
            if merges not in best or cost < best[merges][0]:
                best[merges] = (cost, scale, double // 2)
    return best


class TestWii2dFirstEpochUnaryFloor:
    @pytest.mark.parametrize(("domain", "floor"), [(32, 59), (64, 121)])
    def test_progress_costs_double_the_domain(self, domain: int, floor: int) -> None:
        best = _first_epoch_costs(domain)
        progress = [cost for merges, (cost, _, _) in best.items() if merges >= 3]
        assert min(progress) == floor
        assert all(
            merges <= 2
            for merges, (_, scale, centre) in best.items()
            if scale == 0 and abs(centre) <= 8
        )

    @pytest.mark.parametrize(
        ("domain", "centre", "floor"), [(32, 57, 59), (64, 119, 121)]
    )
    def test_the_shipped_first_fold_pays_the_floor(
        self, domain: int, centre: int, floor: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import importlib

        module = importlib.import_module("esolangs.tools.wii2d")
        seen: list[str] = []

        def capture(
            values: list[int], bits: list[int]
        ) -> list[tuple[int, int, int, str, list[int]]]:
            candidates = _wii2d_folds(values, bits)
            if not seen and candidates:
                seen.append(candidates[0][3])
            return candidates

        monkeypatch.setattr(module, "_wii2d_folds", capture)
        assert _wii2d_decode(_lfsr(domain)) is not None
        pre = seen[0].split("s")[0]
        assert (1 if pre.startswith("*") else 0) + len(pre.lstrip("*")) + 1 == floor
        assert pre.lstrip("*").count("-") == centre
