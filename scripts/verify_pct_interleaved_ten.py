"""Rebuild and execute the seed-31 interleaved-fold construction."""

# ruff: noqa: D103, SLF001
# mypy: disable-error-code="index,no-untyped-call,no-untyped-def,var-annotated"

from __future__ import annotations

import argparse
import importlib
import random

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.pct_squared_minus_one import run

pct = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

_EXPECTED = {
    9: {
        "stages": ((1_419, 14_855), (104, 1_110), (20, 153)),
        "tight": ((16, 15, 73), (4, 3, 9), (2, 1, 2)),
        "template": 349_409,
        "rendered": 349_195,
        "ops": 1_627,
    },
    10: {
        "stages": (
            (16_385, 167_201),
            (2_380, 24_975),
            (118, 1_242),
            (20, 162),
        ),
        "tight": ((96, 169, 488), (16, 15, 69), (4, 3, 8), (2, 1, 2)),
        "template": 1_827_116,
        "rendered": 1_826_806,
        "ops": 19_470,
    },
}


def signature(state):
    """Keep exact geometry and cofactor strings, including their remaining depth."""
    return tuple((point, point_span, cls) for point, point_span, cls, _rows in state)


def search(state, target, *, maxsteps=200_000, kcap=3):
    """Follow the recorded count-first walk without speculative pruning."""
    start = pct._fold_norm(list(state))
    start = tuple(
        (p, point_span, cls, frozenset({index}))
        for index, (p, point_span, cls, _rows) in enumerate(start)
    )
    seen = {signature(start)}
    current = start
    ops = []
    best = start
    steps = 0
    while steps < maxsteps:
        if len(current) == target and pct._cofactor_done(current):
            return ops, current, steps, len(seen)
        choices = []
        for kind, k, amount, rows, nxt in pct._fold_moves(current, kcap=kcap):
            sig = signature(nxt)
            if sig in seen:
                continue
            seen.add(sig)
            choices.append(((kind, k, amount, rows), nxt))
        if not choices:
            return None, best, steps, len(seen)
        # This is the recorded count-first walk.  Python's stable minimum
        # preserves _fold_moves' candidate order for ties.
        op, current = min(choices, key=lambda item: len(item[1]))
        ops.append(op)
        steps += 1
        if steps % 1000 == 0:
            print("progress", steps, len(seen), len(best), flush=True)
        if len(current) < len(best):
            best = current
            print("search", steps, len(seen), len(best), span(best), flush=True)
    return None, best, steps, len(seen)


def span(state):
    return max(p for p, _s, _c, _r in state) - min(p - s for p, s, _c, _r in state)


def tighten(state):
    """Replace each outer gap by one via widen-to-3003/contract-at-cmin."""
    current = state
    ops = []
    seen = {signature(current)}
    guard = 0
    while span(current) > 2 * (len(current) - 1):
        guard += 1
        if guard > 20 * len(current):
            raise AssertionError((len(current), span(current), guard))
        before = span(current)
        candidates = []
        if before > pct._LIMIT:
            # Above 3003, cmin moves an endpoint into the interior and drops
            # precisely that outer gap.  This is the entry phase for a wide
            # compacted state.
            for kind in ("d", "u"):
                op = pct._fold_op(current, kind, 1, pct._LIMIT + 1)
                nxt = pct._fold_step(current, op)
                if (
                    nxt is not None
                    and len(nxt) == len(current)
                    and span(nxt) < before
                    and signature(nxt) not in seen
                ):
                    candidates.append((span(nxt), [op], nxt))
        else:
            # At the 3003-wide frame, repeated cmin contractions sweep the
            # outer gaps in order.  A gap of one leaves the span at exactly
            # 3003 while rotating the next gap to the end; a larger gap
            # performs the geometric contraction.
            for kind in ("d", "u"):
                amount = pct._fold_clean_amount(current, kind, 1)
                if amount is None:
                    continue
                op = pct._fold_op(current, kind, 1, amount)
                nxt = pct._fold_step(current, op)
                if (
                    nxt is not None
                    and len(nxt) == len(current)
                    and span(nxt) <= pct._LIMIT
                    and signature(nxt) not in seen
                ):
                    candidates.append((span(nxt), [op], nxt))
        # A cmin collision at span 3004 is entered through the legal
        # two-step form: widen the endpoint to exactly 3003 at cmax, then
        # contract that same endpoint from the opposite side at cmin.
        for kind, opposite in (("d", "u"), ("u", "d")):
            frame = pct._fold_wipe_frame(current, kind, 1)
            if frame is None:
                continue
            q1, _tops = frame
            widen = pct._fold_op(current, kind, 1, pct._LIMIT + q1)
            widened = pct._fold_step(current, widen)
            if widened is None or span(widened) != pct._LIMIT:
                continue
            amount = pct._fold_clean_amount(widened, opposite, 1)
            if amount is None:
                continue
            contract = pct._fold_op(widened, opposite, 1, amount)
            nxt = pct._fold_step(widened, contract)
            if (
                nxt is not None
                and len(nxt) == len(current)
                and span(nxt) <= pct._LIMIT
                and signature(nxt) not in seen
            ):
                candidates.append((span(nxt), [widen, contract], nxt))
        if not candidates:
            raise AssertionError(
                ("tightening stuck", len(current), before, guard, signature(current))
            )
        _new_span, chosen, current = min(candidates, key=lambda item: item[0])
        ops.extend(chosen)
        seen.add(signature(current))
    return ops, current


def lay(table, n, laid, state):
    amount = span(state) + 2
    out = []
    for point, old_span, _cls, rows in state:
        assert old_span == 0
        for bit in (0, 1):
            picked = frozenset(
                row for row in rows if (row >> (n - 1 - laid)) & 1 == bit
            )
            if picked:
                cls = pct._cofactor_class(table, n, next(iter(picked)), laid + 1)
                assert all(
                    pct._cofactor_class(table, n, row, laid + 1) == cls
                    for row in picked
                )
                out.append((point - amount * bit, 0, cls, picked))
    return pct._fold_norm(out), amount


def replay(state, ops):
    current = state
    full_ops = []
    for op in ops:
        kind, k, amount, _rows = op
        full_op = (
            (kind, k, amount, frozenset())
            if kind == "m"
            else pct._fold_op(current, kind, k, amount)
        )
        nxt = pct._fold_step(current, full_op)
        assert nxt is not None, op
        full_ops.append(full_op)
        current = nxt
    return full_ops, current


def emitter_state(emitter):
    return pct._fold_norm(
        [
            (
                value,
                0,
                emitter.cls[key],
                key if isinstance(key, frozenset) else frozenset({key}),
            )
            for key, value in emitter.pos.items()
        ]
    )


def check_emitter(emitter, state):
    got = emitter_state(emitter)
    assert signature(got) == signature(state)
    assert [rows for *_rest, rows in got] == [rows for *_rest, rows in state]


def emit_ops(emitter, ops):
    for index, (kind, _k, amount, rows) in enumerate(ops):
        if kind == "m":
            emitter.double(
                next_is_rise=index + 1 < len(ops) and ops[index + 1][0] == "u"
            )
        elif kind == "d":
            emitter.dive(amount, rows)
        else:
            emitter.rise(amount, rows)


def lay_emitter(emitter, table, n, index, zero, one):
    next_pos = {}
    next_cls = {}
    for group_key, value in emitter.pos.items():
        raw = set(group_key) if isinstance(group_key, frozenset) else {group_key}
        for bit, code in ((0, zero), (1, one)):
            picked = frozenset(
                row for row in raw if (row >> (n - 1 - index)) & 1 == bit
            )
            if not picked:
                continue
            suffixes = {pct._cofactor_class(table, n, row, index + 1) for row in picked}
            assert len(suffixes) == 1
            key = next(iter(picked)) if len(picked) == 1 else picked
            next_pos[key] = pct._apply(value, code)
            next_cls[key] = next(iter(suffixes))
    emitter.pos, emitter.cls = next_pos, next_cls


def main(n=10, seed=31):
    """Build and execute one recorded arity."""
    assert n in _EXPECTED
    expected = _EXPECTED[n]
    rng = random.Random(seed)
    table = "".join(rng.choice("01") for _ in range(2**n))
    suffix_width = 2 ** (n - 7)
    state = pct._fold_norm(
        [
            (
                -2 * prefix,
                0,
                table[prefix * suffix_width : (prefix + 1) * suffix_width],
                frozenset(range(prefix * suffix_width, (prefix + 1) * suffix_width)),
            )
            for prefix in range(128)
        ]
    )
    weights = pct._fold_uniform(7, 2)
    setters = pct._fold_setters(7, weights)
    emitter = pct._FoldEmitter.__new__(pct._FoldEmitter)
    emitter.table = table
    emitter.rows = 2**n
    emitter.pos = {rows: point for point, _span, _cls, rows in state}
    emitter.cls = {rows: cls for _point, _span, cls, rows in state}
    emitter.body = ["{X" + str(index) + "}" for index in range(7)]
    check_emitter(emitter, state)
    all_ops = []
    for stage_number, laid in enumerate(range(6, n)):
        if laid == 6:
            amount = 2
        else:
            state, amount = lay(table, n, laid, state)
            zero, one = pct._fold_setters(1, (amount,))[0]
            setters.append((zero, one))
            lay_emitter(emitter, table, n, laid, zero, one)
            emitter.body.append("{X" + str(laid) + "}")
            check_emitter(emitter, state)
        target = len({c for _p, _s, c, _r in state})
        print(
            "stage",
            laid,
            "laid",
            len(state),
            "target",
            target,
            "span",
            span(state),
            "setter",
            amount,
            flush=True,
        )
        plan, reached, steps, unique = search(state, target, maxsteps=200_000, kcap=3)
        print(
            "compact",
            laid,
            plan is not None,
            len(reached),
            span(reached),
            steps,
            unique,
            flush=True,
        )
        if plan is None:
            raise AssertionError(("compaction failed", laid, signature(reached)))
        assert (steps, unique) == expected["stages"][stage_number]
        stage_start = state
        full_plan, state = replay(stage_start, plan)
        emit_ops(emitter, full_plan)
        check_emitter(emitter, state)
        all_ops.extend(full_plan)
        tight_ops, state = tighten(state)
        emit_ops(emitter, tight_ops)
        check_emitter(emitter, state)
        all_ops.extend(tight_ops)
        print("tight", laid, len(state), span(state), len(tight_ops), flush=True)
        assert (len(state), span(state), len(tight_ops)) == expected["tight"][
            stage_number
        ]
    emitter.finish()
    header = ";".join(
        f"{index}={zero}|{one}" for index, (zero, one) in enumerate(setters)
    )
    template = header + pct._HEADER_END + "".join(emitter.body)
    widths = set()
    assert len(template) == expected["template"]
    for row in range(2**n):
        bits = [(row >> shift) & 1 for shift in range(n - 1, -1, -1)]
        program = pct.fill(template, bits)
        widths.add(len(program))
        io = ScriptedIO()
        run(program, io)
        assert io.getvalue() == table[row], (row, io.getvalue(), table[row])
        if (row + 1) % 64 == 0:
            print("executed", row + 1, flush=True)
    assert widths == {expected["rendered"]}
    assert len(all_ops) == expected["ops"]
    print(
        "verified",
        n,
        "template",
        len(template),
        "rendered",
        widths,
        "ops",
        len(all_ops),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("n", type=int, nargs="?", choices=(9, 10))
    args = parser.parse_args()
    for arity in (9, 10) if args.n is None else (args.n,):
        main(n=arity)
