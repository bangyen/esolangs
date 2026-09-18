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
    _WII2D_MAX_MAGNITUDE,
    _wii2d_apply,
    _wii2d_compress,
    _wii2d_decode,
    _wii2d_folds,
    _wii2d_offset,
    _wii2d_points,
    _wii2d_threshold,
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


def _legal_prefix_folds(values: list[int], bits: list[int]) -> list[tuple[int, int]]:
    """Return every legal ``(scale, centre)`` first fold, scales 0/1."""
    out: list[tuple[int, int]] = []
    for scale in (0, 1):
        scaled = [value * 2 if scale else value for value in values]
        live = _wii2d_points(scaled, bits)
        if live is None:
            continue
        points = sorted(live)
        zeros = [point for point in points if live[point] == 0]
        ones = [point for point in points if live[point] == 1]
        crossing = {zero + one for zero in zeros for one in ones}
        seen: set[int] = set()
        for group in (zeros, ones):
            for index, first in enumerate(group):
                for second in group[index + 1 :]:
                    double = first + second
                    if double % 2 != 0 or double in crossing or double in seen:
                        continue
                    seen.add(double)
                    out.append((scale, double // 2))
    return out


def _prefix_step(
    values: list[int], bits: list[int], ops: str, scale: int, centre: int
) -> tuple[list[int], str]:
    """Apply one forced fold and its compression, returning the new state."""
    scaled = [value * 2 if scale else value for value in values]
    fragment = ("*" if scale else "") + _wii2d_offset(centre) + "s"
    grown, frag = _wii2d_compress([(v - centre) ** 2 for v in scaled], bits, fragment)
    return grown, ops + frag


def _shipped_tail(values: list[int], bits: list[int], ops: str) -> str | None:
    """Finish a forced prefix with the shipped single-candidate loop."""
    for _ in range(len(bits) + 1):
        live = _wii2d_points(values, bits)
        if live is None:
            return None
        if max(abs(v) for v in values) > _WII2D_MAX_MAGNITUDE:
            return None
        if len(live) <= 2:
            return ops + _wii2d_threshold(live)
        candidates = _wii2d_folds(values, bits)
        if not candidates:
            return None
        *_rank, fragment, values = candidates[0]
        ops += fragment
    return None


def _best_two_prefix(pattern: list[int]) -> tuple[int, str]:
    """Return the shortest replay-verified readout over 1- and 2-fold prefixes.

    Exhaustive over :func:`_legal_prefix_folds` (scales 0/1), each prefix
    finished by :func:`_shipped_tail`.  Test-only oracle: the enumeration is
    the point, so this must never become production code.
    """
    bits = list(pattern)
    values, ops = _wii2d_compress(list(range(len(bits))), bits, "")
    best = _wii2d_decode(bits)
    assert best is not None
    assert [_wii2d_apply(best, v) for v in range(len(bits))] == bits
    for scale1, centre1 in _legal_prefix_folds(values, bits):
        first_values, first_ops = _prefix_step(values, bits, ops, scale1, centre1)
        for scale2, centre2 in _legal_prefix_folds(first_values, bits):
            second_values, second_ops = _prefix_step(
                first_values, bits, first_ops, scale2, centre2
            )
            total = _shipped_tail(second_values, bits, second_ops)
            if total is not None and len(total) < len(best):
                assert [_wii2d_apply(total, v) for v in range(len(bits))] == bits
                best = total
    return len(best), best


class TestWii2dTwoPrefixBeatsShipped:
    """The depth predictor is 20-35% off the two-prefix optimum, systematically.

    Exact minima over every one- and two-fold prefix (scales 0/1) plus the
    shipped tail: 80 vs 110 at domain 16, 282 vs 333 at 32 (1.7-4.1s).  A
    named second pick does not recover it -- extremal-at-step-two gives
    110/311/248/511/246 across five patterns, worse twice -- so the gap is
    search-only: a bigger enumeration, not a rule, and readout stays
    super-linear either way (5.0, 8.8, 14.0 chars/entry at 16/32/64).
    """

    @pytest.mark.parametrize(
        ("domain", "optimum"),
        [
            (16, 80),
            pytest.param(32, 282, marks=pytest.mark.medium),  # 903 prefixes, ~2.5s
        ],
    )
    def test_the_optimum_is_exact_and_shorter(self, domain: int, optimum: int) -> None:
        pattern = _lfsr(domain)
        shipped = _wii2d_decode(pattern)
        assert shipped is not None
        length, _ops = _best_two_prefix(pattern)
        assert length == optimum
        assert length < len(shipped)

    def test_the_shorter_readout_runs_the_full_grid(self) -> None:
        from esolangs.interpreters.grid_based.wii2d import run as run_wii2d
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.wii2d import _wii2d_layout
        from tests.tools.fills import _fill_wii2d

        pattern = _lfsr(16)
        _length, ops = _best_two_prefix(pattern)
        routes = [("*", "*+")] * 4 + [(ops, ops)]
        template = "\n".join(_wii2d_layout(5, 0, routes))
        table = "".join(str(bit) * 2 for bit in pattern)
        for combo in range(32):
            bits = [(combo >> (4 - index)) & 1 for index in range(5)]
            io = ScriptedIO()
            run_wii2d(_fill_wii2d(template, bits).splitlines(), io)
            assert io.getvalue() == table[combo], bits
