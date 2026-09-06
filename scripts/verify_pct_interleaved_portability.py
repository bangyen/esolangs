"""Replay the recorded ten-input %^2^-1 interleaved route portably.

The seed route stays outside the normal generator.  This script records its
literal fold moves once, then replays them on a named family.  State algebra
is insufficient evidence: every completed replay emits a template and runs
all 1,024 input rows.
"""

# ruff: noqa: D103, E501, SLF001
# mypy: disable-error-code="arg-type,index,no-untyped-call,no-untyped-def,type-arg,var-annotated"

from __future__ import annotations

import argparse
import importlib
import os
import pickle
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from _pct_fold import collision_candidates, signature, span

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.pct_squared_minus_one import run

pct = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")

_N = 10
_SEED = 31
_PREFIX = 7
_KCAP = 3
_MAXSTEPS = 200_000
_WORKER_TEMPLATE = ""
_WORKER_TABLE = ""


class Stage(NamedTuple):
    """One input lay and its literal seed moves."""

    laid: int
    setter: int
    compact: tuple[tuple, ...]
    tight: tuple[tuple, ...]
    before: tuple
    traces: tuple[tuple, ...]


@dataclass(frozen=True)
class Route:
    """Hold the concrete moves recorded from the positive control."""

    stages: tuple[Stage, ...]


def seed_table() -> str:
    rng = random.Random(_SEED)
    return "".join(rng.choice("01") for _ in range(2**_N))


def initial_state(table: str):
    width = 2 ** (_N - _PREFIX)
    return pct._fold_norm(
        [
            (
                -2 * prefix,
                0,
                table[prefix * width : (prefix + 1) * width],
                frozenset(range(prefix * width, (prefix + 1) * width)),
            )
            for prefix in range(2**_PREFIX)
        ]
    )


def search(state, target):
    """Follow the recorded count-first seed walk."""
    current = pct._fold_norm(list(state))
    seen = {signature(current)}
    ops = []
    for _ in range(_MAXSTEPS):
        if len(current) == target and pct._cofactor_done(current):
            return tuple(ops)
        choices = []
        for kind, k, amount, rows, nxt in pct._fold_moves(current, kcap=_KCAP):
            if signature(nxt) not in seen:
                seen.add(signature(nxt))
                choices.append(((kind, k, amount, rows), nxt))
        if not choices:
            return None
        op, current = min(choices, key=lambda item: len(item[1]))
        ops.append(op)
    return None


def tighten(state):
    """Apply the seed's deterministic widen/contract gap tightening."""
    current, ops, seen = state, [], {signature(state)}
    while span(current) > 2 * (len(current) - 1):
        before, candidates = span(current), []
        if before > pct._LIMIT:
            for kind in ("d", "u"):
                op = pct._fold_op(current, kind, 1, pct._LIMIT + 1)
                nxt = pct._fold_step(current, op)
                if (
                    nxt is not None
                    and span(nxt) < before
                    and signature(nxt) not in seen
                ):
                    candidates.append((span(nxt), (op,), nxt))
        else:
            for kind in ("d", "u"):
                amount = pct._fold_clean_amount(current, kind, 1)
                if amount is None:
                    continue
                op = pct._fold_op(current, kind, 1, amount)
                nxt = pct._fold_step(current, op)
                if (
                    nxt is not None
                    and span(nxt) <= pct._LIMIT
                    and signature(nxt) not in seen
                ):
                    candidates.append((span(nxt), (op,), nxt))
        # The cmin collision at span 3004, spelled once in _pct_fold.
        candidates.extend(collision_candidates(current, seen))
        if not candidates:
            raise AssertionError(("seed tightening stuck", signature(current)))
        _new_span, chosen, current = min(candidates, key=lambda item: item[0])
        ops.extend(chosen)
        seen.add(signature(current))
    return tuple(ops), current


def lay(table, laid, state):
    amount, out = span(state) + 2, []
    for point, old_span, _cls, rows in state:
        assert old_span == 0
        for bit in (0, 1):
            picked = frozenset(
                row for row in rows if (row >> (_N - 1 - laid)) & 1 == bit
            )
            if picked:
                cls = pct._cofactor_class(table, _N, next(iter(picked)), laid + 1)
                assert all(
                    pct._cofactor_class(table, _N, row, laid + 1) == cls
                    for row in picked
                )
                out.append((point - amount * bit, 0, cls, picked))
    return pct._fold_norm(out), amount


def replay_ops(state, ops):
    traces, current = [], state
    for op in ops:
        traces.append(current)
        current = pct._fold_step(current, op)
        assert current is not None, op
    return current, tuple(traces)


def record_route() -> Route:
    """Search only seed-31 and save exactly the moves it chose."""
    table, state, stages = seed_table(), initial_state(seed_table()), []
    for laid in range(_PREFIX - 1, _N):
        if laid == _PREFIX - 1:
            amount = 2
        else:
            state, amount = lay(table, laid, state)
        compact = search(state, len({cls for _p, _s, cls, _r in state}))
        if compact is None:
            raise AssertionError(("seed compaction failed", laid, signature(state)))
        after_compact, compact_traces = replay_ops(state, compact)
        tight, after_tight = tighten(after_compact)
        after_tight, tight_traces = replay_ops(after_compact, tight)
        stages.append(
            Stage(laid, amount, compact, tight, state, compact_traces + tight_traces)
        )
        state = after_tight
    return Route(tuple(stages))


def pattern(state):
    """Canonical class partition, independent of literal cofactor bits."""
    names, out = {}, []
    for _point, _point_span, cls, _rows in state:
        out.append(names.setdefault(cls, len(names)))
    return tuple(out)


def short(cls):
    return cls if len(cls) <= 16 else cls[:8] + "…" + cls[-8:]


def difference(expected, got):
    cofactor = next(
        (
            f"slot {i}: {short(want[2])} != {short(have[2])}"
            for i, (want, have) in enumerate(zip(expected, got, strict=False))
            if want[2] != have[2]
        ),
        "same slot cofactors"
        if len(expected) == len(got)
        else "different live-point count",
    )
    seed_pattern, replay_pattern = pattern(expected), pattern(got)
    equality = next(
        (
            f"slot {index}: seed class {want}, replay class {have}"
            for index, (want, have) in enumerate(
                zip(seed_pattern, replay_pattern, strict=False)
            )
            if want != have
        ),
        "same class labels"
        if len(seed_pattern) == len(replay_pattern)
        else f"live points seed={len(seed_pattern)} replay={len(replay_pattern)}",
    )
    return (
        f"cofactor {cofactor}; equality-pattern {equality} "
        f"(classes seed={len(set(seed_pattern))} replay={len(set(replay_pattern))})"
    )


def precondition(state, op):
    """Return the first literal route precondition that fails."""
    kind, k, amount, vids = op
    if kind == "m":
        if not 0 < span(state) * 2 <= 2 * pct._LIMIT - 2:
            return f"double spread {span(state)} is outside 1..{pct._LIMIT - 1}"
        return None
    if k > len(state):
        return f"wipe asks for {k} groups but only {len(state)} remain"
    actual = pct._fold_op(state, kind, k, amount)[3]
    if actual != vids:
        return f"victims changed: seed={sorted(vids)} replay={sorted(actual)}"
    if k == len(state):
        if len({cls for _p, _s, cls, _r in state}) != 1:
            return "everything-wipe needs one cofactor class"
        return None
    frame = pct._fold_wipe_frame(state, kind, k)
    if frame is None:
        return "victims are not one cofactor class or have no survivor gap"
    q1, _tops = frame
    if not pct._LIMIT + 1 <= amount <= pct._LIMIT + q1:
        return f"amount {amount} is outside [{pct._LIMIT + 1}, {pct._LIMIT + q1}]"
    if pct._fold_step(state, op) is None:
        return "landing collides across cofactors or exceeds the span bound"
    return None


def make_emitter(table, state):
    out = pct._FoldEmitter.__new__(pct._FoldEmitter)
    out.table, out.rows = table, 2**_N
    out.pos = {rows: point for point, _span, _cls, rows in state}
    out.cls = {rows: cls for _point, _span, cls, rows in state}
    out.body = ["{X" + str(index) + "}" for index in range(_PREFIX)]
    return out


def emit_ops(out, ops):
    for index, (kind, _k, amount, rows) in enumerate(ops):
        if kind == "m":
            out.double(next_is_rise=index + 1 < len(ops) and ops[index + 1][0] == "u")
        elif kind == "d":
            out.dive(amount, rows)
        else:
            out.rise(amount, rows)


def prepare_worker(template, table):
    """Install one completed template in an interpreter worker."""
    global _WORKER_TABLE, _WORKER_TEMPLATE
    _WORKER_TEMPLATE, _WORKER_TABLE = template, table


def execute_row(row):
    """Run one truth-table address through the completed template."""
    bits = [(row >> shift) & 1 for shift in range(_N - 1, -1, -1)]
    io = ScriptedIO()
    run(pct.fill(_WORKER_TEMPLATE, bits), io)
    return row, io.getvalue()


def lay_emitter(out, table, laid, amount):
    zero, one = pct._fold_setters(1, (amount,))[0]
    next_pos, next_cls = {}, {}
    for key, value in out.pos.items():
        raw = set(key) if isinstance(key, frozenset) else {key}
        for bit, code in ((0, zero), (1, one)):
            picked = frozenset(
                row for row in raw if (row >> (_N - 1 - laid)) & 1 == bit
            )
            if picked:
                key2 = next(iter(picked)) if len(picked) == 1 else picked
                next_pos[key2] = pct._apply(value, code)
                next_cls[key2] = pct._cofactor_class(
                    table, _N, next(iter(picked)), laid + 1
                )
    out.pos, out.cls = next_pos, next_cls
    out.body.append("{X" + str(laid) + "}")
    return zero, one


def execute(label, table, route, rows) -> bool:
    """Replay a table; completions emit a template and execute every row."""
    state, out = initial_state(table), make_emitter(table, initial_state(table))
    setters = pct._fold_setters(_PREFIX, pct._fold_uniform(_PREFIX, 2))
    for stage in route.stages:
        if stage.laid != _PREFIX - 1:
            state, amount = lay(table, stage.laid, state)
            if amount != stage.setter:
                print(
                    f"{label}: stage {stage.laid} FAIL setter "
                    f"seed={stage.setter} replay={amount}; "
                    f"{difference(stage.before, state)}"
                )
                return False
            setters.append(lay_emitter(out, table, stage.laid, amount))
        ops = stage.compact + stage.tight
        for move_index, op in enumerate(ops):
            failed = precondition(state, op)
            if failed is not None:
                phase = "compact" if move_index < len(stage.compact) else "tight"
                print(
                    f"{label}: stage {stage.laid} {phase} move {move_index} "
                    f"FAIL {failed}; {difference(stage.traces[move_index], state)}"
                )
                return False
            state = pct._fold_step(state, op)
            assert state is not None
        emit_ops(out, ops)
        print(
            f"{label}: stage {stage.laid} complete "
            f"({len(state)} classes, span {span(state)})"
        )
    out.finish()
    header = ";".join(
        f"{index}={zero}|{one}" for index, (zero, one) in enumerate(setters)
    )
    template = header + pct._HEADER_END + "".join(out.body)
    workers = min(8, os.cpu_count() or 1)
    with ProcessPoolExecutor(
        max_workers=workers, initializer=prepare_worker, initargs=(template, table)
    ) as pool:
        for row, value in pool.map(execute_row, rows):
            assert value == table[row], (label, row, value, table[row])
    print(f"{label}: COMPLETE template={len(template)} executed={len(rows)}")
    return True


def permute_inputs(table, order):
    return "".join(
        table[
            sum(
                ((row >> (_N - 1 - dst)) & 1) << (_N - 1 - src)
                for dst, src in enumerate(order)
            )
        ]
        for row in range(2**_N)
    )


def family():
    """Yield complement, permutations, and dense tables as a fixed family."""
    seed = seed_table()
    yield "seed-31", seed
    yield "seed-31-complement", "".join("1" if bit == "0" else "0" for bit in seed)
    yield "perm-reverse", permute_inputs(seed, tuple(reversed(range(_N))))
    for shift in (1, 3, 7):
        yield (
            f"perm-rotate-{shift}",
            permute_inputs(seed, tuple((i + shift) % _N for i in range(_N))),
        )
    for dense_seed in (1, 17, 101):
        rng = random.Random(dense_seed)
        yield f"dense-{dense_seed}", "".join(rng.choice("01") for _ in range(2**_N))


def replay_family(route, labels, rows):
    """Replay one already-recorded route over the fixed portability family."""
    moves = sum(len(stage.compact) + len(stage.tight) for stage in route.stages)
    print(f"recorded seed-31: stages={len(route.stages)} moves={moves}")
    completed = [
        label
        for label, table in family()
        if (not labels or label in labels) and execute(label, table, route, rows)
    ]
    print("completed:", ", ".join(completed) if completed else "none")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--record", type=Path, metavar="PATH")
    group.add_argument("--replay", type=Path, metavar="PATH")
    parser.add_argument("--only", action="append", metavar="LABEL")
    parser.add_argument("--rows", default="0:1024", metavar="START:STOP")
    args = parser.parse_args()
    start_text, stop_text = args.rows.split(":", maxsplit=1)
    rows = range(int(start_text), int(stop_text))
    if not 0 <= rows.start <= rows.stop <= 2**_N:
        parser.error("--rows must be within 0:1024")
    if args.record is not None:
        route = record_route()
        args.record.write_bytes(pickle.dumps(route))
        print(f"recorded route: {args.record}")
    elif args.replay is not None:
        replay_family(pickle.loads(args.replay.read_bytes()), args.only, rows)
    else:
        replay_family(record_route(), args.only, rows)
