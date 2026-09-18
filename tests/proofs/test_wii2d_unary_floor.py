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


def _cheapest_progressive_on_path(domain: int) -> tuple[int, int]:
    """Return ``(live, cost)`` of the cheapest 3+-merge fold one step in.

    Replays the shipped decoder's own first fold on the LFSR witness, then
    exhausts scales 0/1 for the cheapest legal next fold merging 3+ values.
    Cost is the unary spelling ``scale + |centre| + 1``.
    """
    pattern = _lfsr(domain)
    bits = list(pattern)
    values, _ops = _wii2d_compress(list(range(domain)), bits, "")
    values = _wii2d_folds(values, bits)[0][4]
    stepped = _wii2d_points(values, bits)
    assert stepped is not None  # the shipped winner is legal by construction
    live = len(stepped)
    best: int | None = None
    for scale in (0, 1):
        scaled = [value * 2 if scale else value for value in values]
        state = _wii2d_points(scaled, bits)
        assert state is not None
        points = sorted(state)
        zeros = [point for point in points if state[point] == 0]
        ones = [point for point in points if state[point] == 1]
        crossing = {zero + one for zero in zeros for one in ones}
        merging: dict[int, int] = {}
        for group in (zeros, ones):
            for index, first in enumerate(group):
                for second in group[index + 1 :]:
                    double = first + second
                    if double % 2 != 0 or double in crossing:
                        continue
                    merging[double] = merging.get(double, 0) + 1
        for double, merges in merging.items():
            if merges >= 3:
                cost = scale + abs(double // 2) + 1
                if best is None or cost < best:
                    best = cost
    assert best is not None
    return live, best


class TestWii2dNoPerEpochFloor:
    """Later epochs go cheap, so the first-fold floor does not lift.

    One shipped step in, a 3+-merge fold costs 7 at live 28 (domain 32) and
    at live 59 (domain 64) -- far under ``live / 2``. The ratchet is
    cumulative unary-centre spend, not a per-epoch price: pinning this kills
    the ``every progressive epoch pays Omega(live)`` induction, which is why
    the readout bound stays an executed obstruction rather than a proof.
    """

    @pytest.mark.parametrize(("domain", "live", "cost"), [(32, 28, 7), (64, 59, 7)])
    def test_a_progressive_fold_costs_single_digits(
        self, domain: int, live: int, cost: int
    ) -> None:
        assert _cheapest_progressive_on_path(domain) == (live, cost)


#: Three 16-bit draws from ``random.Random(3)`` (D<=16 adaptation of the
#: notes' rand32 trio); literals so the pin does not depend on the RNG.
_WII2D_FRAG_RAND16: tuple[tuple[int, ...], ...] = (
    (0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0),
    (1, 0, 0, 0, 0, 1, 0, 1, 1, 1, 1, 1, 1, 0, 1, 0),
    (0, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 1, 0),
)


def _frag_ranker_pick(values: list[int], bits: list[int]) -> tuple[int, int, int]:
    """Return the ``(scale, centre, merges)`` top-1 by local pair count.

    Scores each legal first fold (scales 0/1) by its same-bit pair count
    only -- no :func:`_wii2d_folds`, no depth, no compress, no tail
    simulation; ties break on ``scale + |centre| + 1``, scale, centre.
    """
    best: tuple[int, int, int] | None = None
    best_key: tuple[int, int, int, int] | None = None
    for scale in (0, 1):
        scaled = [value * 2 if scale else value for value in values]
        live = _wii2d_points(scaled, bits)
        if live is None:
            continue
        points = sorted(live)
        zeros = [point for point in points if live[point] == 0]
        ones = [point for point in points if live[point] == 1]
        crossing = {zero + one for zero in zeros for one in ones}
        merging: dict[int, int] = {}
        for group in (zeros, ones):
            for index, first in enumerate(group):
                for second in group[index + 1 :]:
                    double = first + second
                    if double % 2 != 0 or double in crossing:
                        continue
                    merging[double] = merging.get(double, 0) + 1
        for double, merges in merging.items():
            centre = double // 2
            key = (-merges, scale + abs(centre) + 1, scale, centre)
            if best_key is None or key < best_key:
                best_key = key
                best = (scale, centre, merges)
    assert best is not None
    return best


def _frag_ranker_decode(pattern: list[int]) -> tuple[tuple[int, int, int], str]:
    """Force the loop-less top-1 first fold, then finish by shipped tail."""
    bits = list(pattern)
    values, ops = _wii2d_compress(list(range(len(bits))), bits, "")
    scale, centre, merges = _frag_ranker_pick(values, bits)
    stepped, grown = _prefix_step(values, bits, ops, scale, centre)
    total = _shipped_tail(stepped, bits, grown)
    assert total is not None
    assert [_wii2d_apply(total, v) for v in range(len(bits))] == bits
    return (scale, centre, merges), total


def _ranker_folds(values: list[int], bits: list[int]) -> list[tuple[int, ...]]:
    """Return loop-less ``(scale, centre, merges, cost, frags, drop)`` per legal fold.

    Uses only :func:`_wii2d_points` plus set arithmetic -- no
    :func:`_wii2d_folds`, no depth, no compress or tail simulation.
    ``drop == merges`` and ``frags == live - merges`` for legal square
    folds (pairs are disjoint), so three of the four scorers below rank
    identically; the sweep records that instead of hiding it.
    """
    live0 = _wii2d_points(values, bits)
    assert live0 is not None
    count = len(live0)
    out: list[tuple[int, ...]] = []
    for scale in (0, 1):
        scaled = [value * 2 if scale else value for value in values]
        live = _wii2d_points(scaled, bits)
        if live is None:
            continue
        points = sorted(live)
        zeros = [point for point in points if live[point] == 0]
        ones = [point for point in points if live[point] == 1]
        crossing = {zero + one for zero in zeros for one in ones}
        merging: dict[int, int] = {}
        for group in (zeros, ones):
            for index, first in enumerate(group):
                for second in group[index + 1 :]:
                    double = first + second
                    if double % 2 != 0 or double in crossing:
                        continue
                    merging[double] = merging.get(double, 0) + 1
        for double, merges in merging.items():
            centre = double // 2
            cost = scale + abs(centre) + 1
            frags = len({(value - centre) ** 2 for value in scaled})
            out.append((scale, centre, merges, cost, frags, count - frags))
    return out


def _ranker_pick(
    folds: list[tuple[int, ...]], scorer: str, tiebreak: str
) -> tuple[int, ...]:
    """Return the top-1 fold under ``scorer`` (merge/frag/ratio/drop) and tie-break."""
    best: tuple[int, ...] | None = None
    best_key: tuple[float, int, int, int] | None = None
    for scale, centre, merges, cost, frags, drop in folds:
        if scorer == "merge":
            primary = float(-merges)
        elif scorer == "frag":
            primary = float(frags)
        elif scorer == "ratio":
            primary = -merges / cost
        else:
            assert scorer == "drop"
            primary = float(-drop)
        tie = (
            (cost, scale, centre)
            if tiebreak == "cheap"
            else (-abs(centre), scale, -centre)
        )
        key = (primary, *tie)
        if best_key is None or key < best_key:
            best_key = key
            best = (scale, centre, merges, cost, frags, drop)
    assert best is not None
    return best


def _ranker_decode(
    pattern: list[int], scorer: str, tiebreak: str
) -> tuple[tuple[int, ...], str]:
    """Force the loop-less top-1 first fold, then finish by shipped tail."""
    bits = list(pattern)
    values, ops = _wii2d_compress(list(range(len(bits))), bits, "")
    scale, centre = _ranker_pick(_ranker_folds(values, bits), scorer, tiebreak)[:2]
    stepped, grown = _prefix_step(values, bits, ops, scale, centre)
    total = _shipped_tail(stepped, bits, grown)
    assert total is not None
    assert [_wii2d_apply(total, v) for v in range(len(bits))] == bits
    return (scale, centre), total


def _lookahead_decode(pattern: list[int]) -> tuple[tuple[int, ...], str]:
    """Rank step-1 top-3 (ratio, cheap) by a local one-step lookahead.

    Estimate per first fold is ``cost1 + min(cost2 - merges2)`` over legal
    second folds -- no :func:`_shipped_tail` in the ranking, local only.
    """
    bits = list(pattern)
    values, ops = _wii2d_compress(list(range(len(bits))), bits, "")
    folds = _ranker_folds(values, bits)
    ordered = sorted(
        folds, key=lambda fold: (-fold[2] / fold[3], fold[3], fold[0], fold[1])
    )
    best: tuple[int, ...] | None = None
    best_key: tuple[int, int, int, int] | None = None
    for fold in ordered[:3]:
        scale, centre, _merges, cost = fold[0], fold[1], fold[2], fold[3]
        stepped, _grown = _prefix_step(values, bits, ops, scale, centre)
        seconds = _ranker_folds(stepped, bits)
        estimate = cost if not seconds else cost + min(s[3] - s[2] for s in seconds)
        key = (estimate, cost, scale, centre)
        if best_key is None or key < best_key:
            best_key = key
            best = (scale, centre)
    assert best is not None
    scale, centre = best
    stepped, grown = _prefix_step(values, bits, ops, scale, centre)
    total = _shipped_tail(stepped, bits, grown)
    assert total is not None
    assert [_wii2d_apply(total, v) for v in range(len(bits))] == bits
    return best, total


class TestWii2dRankerSweep:
    """No loop-less step-1 scorer and no local lookahead recovers the prefix gap.

    Four scorers (merge/frag/ratio/drop) by two tie-breaks (cheap/far) on
    LFSR-8/16/32 plus two rand16 literals, replay-verified, D<=32: best
    (merge/frag/drop by cheap) is 29/110/333/63/63 vs shipped
    30/110/333/63/63 -- one cell, LFSR-16 still 30 over the pinned 80-pair
    optimum. Worst (ratio by cheap) blows LFSR-32 to 467 and R1 to 74.
    A local one-step lookahead over the step-1 top-3 fires yet gives
    115 on LFSR-16 (merge base: 115/110), recovering nothing. Third-clause
    standing with the frag-pair pin: the gap needs the pair search itself.
    """

    @pytest.mark.parametrize(
        ("pattern", "shipped", "ranked"),
        [
            pytest.param(tuple(_lfsr(8)), 30, 29, id="lfsr8"),
            pytest.param(tuple(_lfsr(16)), 110, 110, id="lfsr16"),
            pytest.param(tuple(_lfsr(32)), 333, 333, id="lfsr32"),
            pytest.param(_WII2D_FRAG_RAND16[0], 63, 63, id="rand0"),
            pytest.param(_WII2D_FRAG_RAND16[1], 63, 63, id="rand1"),
        ],
    )
    def test_the_best_step1_scorer_gains_one_cell(
        self, pattern: tuple[int, ...], shipped: int, ranked: int
    ) -> None:
        bits = list(pattern)
        decoded = _wii2d_decode(bits)
        assert decoded is not None
        assert [_wii2d_apply(decoded, v) for v in range(len(bits))] == bits
        assert len(decoded) == shipped
        _pick, total = _ranker_decode(bits, "merge", "cheap")
        assert len(total) == ranked
        assert len(decoded) - len(total) <= 1  # never a >=10% recovery

    @pytest.mark.parametrize(
        ("pattern", "shipped", "ranked"),
        [
            pytest.param(tuple(_lfsr(32)), 333, 467, id="lfsr32"),
            pytest.param(_WII2D_FRAG_RAND16[1], 63, 74, id="rand1"),
        ],
    )
    def test_the_ratio_scorer_goes_backwards(
        self, pattern: tuple[int, ...], shipped: int, ranked: int
    ) -> None:
        bits = list(pattern)
        assert len(_wii2d_decode(bits) or "") == shipped
        pick, total = _ranker_decode(bits, "ratio", "cheap")
        assert len(total) == ranked
        assert pick == ((0, 2) if len(bits) == 32 else (1, 5))  # fires, loses

    def test_the_lookahead_fires_yet_misses_the_optimum(self) -> None:
        bits = _lfsr(16)
        top1, _tail = _ranker_decode(bits, "ratio", "cheap")
        pick, total = _lookahead_decode(bits)
        assert top1 == (0, 2)  # step-1 top-1 stays
        assert pick == (0, 1)  # lookahead fires: leaves the top-1
        assert len(total) == 115  # 35 over the pinned 80-pair optimum

    def test_the_scoring_uses_no_folds_depth_or_tail(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import importlib

        module = importlib.import_module("esolangs.tools.wii2d")

        def refuse(*_args: object) -> object:
            raise AssertionError("tail simulation in a loop-less scorer")

        monkeypatch.setattr(module, "_wii2d_folds", refuse)
        monkeypatch.setattr(module, "_wii2d_depth", refuse)
        bits = _lfsr(16)
        values, _ops = _wii2d_compress(list(range(16)), bits, "")
        folds = _ranker_folds(values, bits)
        assert _ranker_pick(folds, "merge", "cheap")[:2] == (0, 2)
        assert _ranker_pick(folds, "merge", "far")[:2] == (1, 4)  # tie-break fires

    def test_the_best_readout_runs_the_full_grid(self) -> None:
        from esolangs.interpreters.grid_based.wii2d import run as run_wii2d
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.wii2d import _wii2d_layout
        from tests.tools.fills import _fill_wii2d

        pattern = _lfsr(16)
        _pick, ops = _ranker_decode(pattern, "merge", "cheap")
        routes = [("*", "*+")] * 4 + [(ops, ops)]
        template = "\n".join(_wii2d_layout(5, 0, routes))
        table = "".join(str(bit) * 2 for bit in pattern)
        for combo in range(32):
            bits = [(combo >> (4 - index)) & 1 for index in range(5)]
            io = ScriptedIO()
            run_wii2d(_fill_wii2d(template, bits).splitlines(), io)
            assert io.getvalue() == table[combo], bits

    """A loop-less pair-count first fold recovers none of the prefix gap.

    Top-1 by local same-bit pair count (no tail simulation) plus shipped
    tail, replay-verified: 110/29/63/63/128 vs shipped 110/30/63/63/115
    (LFSR-16, LFSR-8, three rand16). Max gain one cell; LFSR-16 misses the
    pinned 80-pair optimum by 30 and R2 goes backwards by 13. The 7-27%
    two-prefix gap needs the pair search itself, like the extremal-at-
    step-two hybrid before it: third-clause standing, no construction.
    """

    @pytest.mark.parametrize(
        ("pattern", "shipped", "ranked"),
        [
            pytest.param(tuple(_lfsr(16)), 110, 110, id="lfsr16"),
            pytest.param(tuple(_lfsr(8)), 30, 29, id="lfsr8"),
            pytest.param(_WII2D_FRAG_RAND16[0], 63, 63, id="rand0"),
            pytest.param(_WII2D_FRAG_RAND16[1], 63, 63, id="rand1"),
            pytest.param(_WII2D_FRAG_RAND16[2], 115, 128, id="rand2"),
        ],
    )
    def test_pair_count_recovers_nothing(
        self, pattern: tuple[int, ...], shipped: int, ranked: int
    ) -> None:
        bits = list(pattern)
        decoded = _wii2d_decode(bits)
        assert decoded is not None
        assert [_wii2d_apply(decoded, v) for v in range(len(bits))] == bits
        assert len(decoded) == shipped
        _pick, total = _frag_ranker_decode(bits)
        assert len(total) == ranked
        assert len(decoded) - len(total) <= 1  # never a >=10% recovery

    def test_the_ranker_fires_yet_misses_the_optimum(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import importlib

        module = importlib.import_module("esolangs.tools.wii2d")
        seen: list[str] = []

        def capture(
            values: list[int], bits: list[int]
        ) -> list[tuple[int, int, int, str, list[int]]]:
            candidates = _wii2d_folds(values, bits)
            if len(seen) < 1 and candidates:
                seen.append(candidates[0][3])
            return candidates

        monkeypatch.setattr(module, "_wii2d_folds", capture)
        assert _wii2d_decode(_lfsr(16)) is not None
        bits = _lfsr(16)
        (scale, centre, merges), total = _frag_ranker_decode(bits)
        assert (scale, centre, merges) == (0, 2, 2)  # max-merge, cheapest
        assert seen
        assert seen[0].startswith("*")  # shipped goes scaled: fires
        assert len(total) == 110  # 30 over the pinned 80-pair optimum

    def test_the_ranked_readout_runs_the_full_grid(self) -> None:
        from esolangs.interpreters.grid_based.wii2d import run as run_wii2d
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.wii2d import _wii2d_layout
        from tests.tools.fills import _fill_wii2d

        pattern = _lfsr(16)
        _pick, ops = _frag_ranker_decode(pattern)
        routes = [("*", "*+")] * 4 + [(ops, ops)]
        template = "\n".join(_wii2d_layout(5, 0, routes))
        table = "".join(str(bit) * 2 for bit in pattern)
        for combo in range(32):
            bits = [(combo >> (4 - index)) & 1 for index in range(5)]
            io = ScriptedIO()
            run_wii2d(_fill_wii2d(template, bits).splitlines(), io)
            assert io.getvalue() == table[combo], bits
