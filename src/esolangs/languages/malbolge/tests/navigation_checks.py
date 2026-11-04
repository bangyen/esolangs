"""Navigation costs against uncached rules and emitted native transitions."""

from __future__ import annotations

import pytest

from esolangs.languages.malbolge.generator import emitter as e
from esolangs.languages.malbolge.generator.emitter import (
    _CYCLE,
    _INF,
    _SUCC,
    _MemTables,
    _Planner,
    _pred_tables,
    _ScanGreedy,
    _valid_chars,
)
from esolangs.languages.malbolge.generator.isa import _char_for, _g
from esolangs.languages.malbolge.interpreter import _advance


def _follow(nav: _ScanGreedy, pos: int) -> int | None:
    if nav.target not in _CYCLE:
        return None
    seen = set()
    while pos != nav.target:
        if pos in seen or pos not in _SUCC or nav.jump[pos] != _SUCC[pos]:
            return None
        seen.add(pos)
        pos = _SUCC[pos]
    return len(seen)


def _walk(nav: _ScanGreedy, pos: int) -> int:
    if pos <= nav.target:
        return nav.target - pos
    cell = next(
        a
        for a in range(nav.ceiling, nav.ceiling + 94)
        if min(_valid_chars(a)) + 1 <= nav.target
    )
    return cell - pos + 1 + nav.target - (min(_valid_chars(cell)) + 1)


def _chain(nav: _ScanGreedy, pos: int, limit: int, step) -> int:
    best, cost, seen = _walk(nav, pos), 0, set()
    while pos not in seen and cost < limit:
        seen.add(pos)
        move = step(pos)
        if move is None:
            break
        length, pos = move
        cost += length
        best = min(best, cost + _walk(nav, pos))
    return best


def _near(nav: _ScanGreedy, pos: int, width: int) -> list[tuple[int, int]]:
    return [
        (q - pos + 1, dest)
        for q in range(pos, min(pos + width + 1, nav.ceiling))
        if (dest := nav.jump[q]) is not None
    ]


def _u(nav: _ScanGreedy, pos: int) -> int:
    follow = _follow(nav, pos)
    return min(
        _walk(nav, pos),
        _INF if follow is None else follow,
        *(cost + _walk(nav, dest) for cost, dest in _near(nav, pos, 3)),
    )


def _step(nav: _ScanGreedy, index: int, pos: int) -> tuple[int, int] | None:
    candidates = []
    for q in range(pos, nav.ceiling):
        dest = nav.jump[q]
        if dest is None:
            continue
        valid = (
            q == pos
            if index == 0
            else q == pos + index
            if index <= 3
            else nav.mem[q] == _g(q)
            if index == 4
            else nav.target - 32 < dest <= nav.target
            if index == 5
            else nav.target - 94 < dest <= nav.target
            if index == 6
            else dest in _CYCLE.get(nav.target, ((), 0))[0]
            if index == 7
            else dest > nav.target
            if index == 8
            else dest < pos
            if index == 9
            else q <= pos + 2
            if index == 10
            else q <= pos + 4
        )
        if valid:
            candidates.append((q - pos + 1, dest))
    if not candidates:
        return None
    return (
        min(candidates, key=lambda v: v[0] + _u(nav, v[1]))
        if index == 11
        else candidates[0]
    )


def _value(nav: _ScanGreedy, pos: int) -> int:
    values = [_u(nav, pos)]
    values.extend(
        _chain(nav, pos, 64, lambda p, nav=nav, i=i: _step(nav, i, p))
        for i in range(12)
    )
    for q in range(pos, nav.ceiling):
        if nav.mem.get(q) == _g(q):
            dest = _g(q) + 1
            if dest == nav.target:
                values.append(q - pos + 1)
            if nav.target in _CYCLE:
                for k in range(1, 6):
                    cycle, index = _CYCLE[nav.target]
                    pred = cycle[(index - k) % len(cycle)]
                    if dest == pred:
                        steps, cur = 0, pred
                        while (
                            steps < k
                            and cur != nav.target
                            and nav.jump[cur] == _SUCC[cur]
                        ):
                            cur = _SUCC[cur]
                            steps += 1
                        values.append(q - pos + 1 + steps + _walk(nav, cur))
    for cost, dest in _near(nav, pos, 21):
        follow = _follow(nav, dest)
        finish = min(
            _walk(nav, dest),
            _chain(nav, dest, 20, lambda p, nav=nav: _step(nav, 0, p)),
            _INF if follow is None else follow,
        )
        values.append(cost + finish)
    return min(values)


def _check_costs() -> None:
    cycle, index = _CYCLE[34]
    predecessor = cycle[(index - 21) % len(cycle)]
    cycle_nav = _ScanGreedy({q: _g(q) for q in cycle}, 34, ceiling=420)
    assert cycle_nav.chain0(predecessor) > 21
    assert cycle_nav.finish(predecessor) == 21
    assert _follow(cycle_nav, predecessor) == 21
    ceiling = 420
    memories = (
        {},
        {q: _g(q) for q in range(ceiling)},
        {0: None, -1: 40, 420: 50, 1: 419, 2: 299, 3: 34, 4: 40, 6: 310},
        {q: (q * 73 + 19) % 419 for q in range(0, ceiling, 3)},
    )
    for mem in memories:
        for target in (34, 40, 95, 127, 310, 430):
            nav = _ScanGreedy(mem, target, ceiling=ceiling)
            for pos in (0, 2, 34, 39, 40, 94, 126, 298, 310, 419):
                assert nav.walk(pos) == _walk(nav, pos)
                assert nav.cycle_follow(pos) == _follow(nav, pos)
                expected = _value(nav, pos)
                for cap in (0, 1, 3, 19, _INF):
                    assert nav.value(pos, cap) == min(cap, expected)
                assert nav.value(pos) == expected  # exact-cache hit
                chain = _chain(nav, pos, 20, lambda p, nav=nav: _step(nav, 0, p))
                first = _chain(
                    nav,
                    pos,
                    30,
                    lambda p, nav=nav, target=target: next(
                        (
                            (q - p + 1, dest)
                            for q in range(p, ceiling)
                            if (dest := nav.jump[q]) is not None and dest <= target
                        ),
                        None,
                    ),
                )
                follow = _follow(nav, pos)
                finish = min(_walk(nav, pos), chain, _INF if follow is None else follow)
                for _ in range(2):
                    assert nav.chain0(pos) == chain
                    assert nav.first_le(pos) == first
                    assert nav.finish(pos) == finish
                assert nav._chains_value(pos, _INF) == min(
                    _chain(nav, pos, 64, lambda p, nav=nav, i=i: _step(nav, i, p))
                    for i in range(12)
                )


def _check_updates() -> None:
    mem: dict[int, int | None] = {q: _g(q) for q in range(420)}
    tables = _MemTables(mem, 420)
    for cell, value in (
        (-1, 0),
        (420, 0),
        (3, 299),
        (3, 310),
        (3, 40),
        (3, None),
        (3, 299),
        (3, None),
        (3, 40),
        (3, _g(3)),
    ):
        tables.update(cell, value)
        if 0 <= cell < 420:
            mem[cell] = value
        rebuilt = _MemTables(mem, 420)
        assert vars(tables) == vars(rebuilt)


def _check_eviction(monkeypatch) -> None:
    # Fill only cache metadata; no 4097-navigation construction or search.
    monkeypatch.setattr(e, "_PRED_TABLES", dict.fromkeys(range(4097)))
    monkeypatch.setattr(e, "_WALK_ALL", dict.fromkeys(range(4097)))
    expected = _pred_tables(5000)
    assert list(e._PRED_TABLES) == [5000]
    assert _pred_tables(5000) is expected
    nav = _ScanGreedy({}, 430, ceiling=420)
    assert list(e._WALK_ALL) == [(430, 420)]
    assert nav.walk(419) == 11


def _check_walk(start: int, target: int) -> None:
    planner = _Planner(2000, start, {}, {}, ceiling=420)
    assert planner._walk_to(start, target) == target
    _execute(planner, start, target)


def _execute(planner: _Planner, start: int, target: int) -> None:
    memory = [0] * 59049
    for cell, value in planner.mem.items():
        if value is not None:
            memory[cell] = value
    for cell, op in planner.code.items():
        memory[cell] = _char_for(op, cell)
    for cell, value in planner.data.items():
        memory[cell] = value
    state = (0, 2000, start, False)
    for _ in planner.code:
        state, writes, effect = _advance(state, memory)
        assert effect is None
        assert not state[-1]
        for cell, value in writes:
            memory[cell] = value
    assert state[2] == target


def _check_jump_limit() -> None:
    planner = _Planner(2000, 0, {q: q + 1 for q in range(80)}, {}, ceiling=420)
    planner.goto(80)
    assert list(planner.code.values()) == ["j"] * 17 + ["o"] * 46
    _execute(planner, 0, 80)


def check_navigation() -> None:
    _check_costs()
    _check_updates()
    with pytest.MonkeyPatch.context() as patch:
        _check_eviction(patch)
    for start, target in ((450, 40), (419, 34), (300, 310), (40, 40)):
        _check_walk(start, target)
    _check_jump_limit()
