"""Enumerative search over gadget programs, with exact certification.

During search, candidates are filtered row by row with early exit:
rows are evaluated in discriminating-power order and the first row
that cannot lead to acceptance rejects the candidate, so most
candidates die on their first rows.  Row order never changes a
verdict, only how soon a bad candidate dies.  A candidate that passes
the filter is only a probable winner until :func:`certify` re-verifies
it against the full spec with the plain simulator, collecting every
row's observable before judging; nothing is a result without that
second, independent check.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass

from .machine import CRAZY0, State, run, step


@dataclass(frozen=True)
class Spec:
    """One row per input: a start state, its input bits, its verdict rule.

    The observable of a final state is its cells at ``observe``.  A row
    passes when its observable equals ``expected`` (unless that is
    ``None``); with ``distinct`` the observables must be pairwise
    distinct across rows.
    """

    starts: tuple[State, ...]
    inputs: tuple[tuple[int, ...], ...]
    expected: tuple[tuple[int, ...] | None, ...]
    distinct: bool
    observe: tuple[int, ...] = (1, 2)


@dataclass
class Stats:
    """Search counters: candidates leaf-evaluated, rows actually run."""

    candidates: int = 0
    rows_evaluated: int = 0


def _observable(state: State, observe: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(state[1][i] for i in observe)


def order_rows(spec: Spec) -> tuple[int, ...]:
    """Row indices by discriminating power, most discriminating first.

    For a distinctness spec, rows whose start observable is shared with
    other rows carry the separation burden, so they are checked first;
    for an equality spec, rows with the rarest expected observable come
    first.  Heuristic only: it affects speed, never the verdict.
    """
    if spec.distinct:
        counts = Counter(_observable(s, spec.observe) for s in spec.starts)
        return tuple(
            sorted(
                range(len(spec.starts)),
                key=lambda i: (-counts[_observable(spec.starts[i], spec.observe)], i),
            )
        )
    want_counts: Counter[tuple[int, ...] | None] = Counter(spec.expected)
    return tuple(
        sorted(
            range(len(spec.starts)), key=lambda i: (want_counts[spec.expected[i]], i)
        )
    )


def _accepts(
    finals: tuple[State, ...],
    spec: Spec,
    order: tuple[int, ...],
    stats: Stats | None = None,
) -> bool:
    """Early-exit verdict on final states, rows checked in ``order``."""
    seen: set[tuple[int, ...]] = set()
    for i in order:
        if stats is not None:
            stats.rows_evaluated += 1
        obs = _observable(finals[i], spec.observe)
        want = spec.expected[i]
        if want is not None and obs != want:
            return False
        if spec.distinct:
            if obs in seen:
                return False
            seen.add(obs)
    return True


def _finals(program: tuple[str, ...], spec: Spec) -> tuple[State, ...]:
    return tuple(
        run(program, bits, start)
        for start, bits in zip(spec.starts, spec.inputs, strict=True)
    )


def evaluate(program: tuple[str, ...], spec: Spec, stats: Stats | None = None) -> bool:
    """Run ``program`` on every row and judge it with early exit."""
    return _accepts(_finals(program, spec), spec, order_rows(spec), stats)


def certify(program: tuple[str, ...], spec: Spec) -> bool:
    """Re-verify ``program`` against the full spec, exactly.

    Independent of the search filter: every row is run with the plain
    simulator, all observables are collected, and only then judged.
    """
    observables = [_observable(f, spec.observe) for f in _finals(program, spec)]
    if spec.distinct and len(set(observables)) != len(observables):
        return False
    return all(
        want is None or obs == want
        for obs, want in zip(observables, spec.expected, strict=True)
    )


@dataclass(frozen=True)
class SearchResult:
    """The first length with hits, and every hit at that length."""

    length: int | None
    hits: tuple[tuple[str, ...], ...]


#: A search row in flight: its current state and how many bits it read.
type _Row = tuple[State, int]


def _step_rows(rows: tuple[_Row, ...], spec: Spec, op: str) -> tuple[_Row, ...] | None:
    """Advance every row by ``op``; ``None`` if a read runs dry."""
    out: list[_Row] = []
    for (state, pos), bits in zip(rows, spec.inputs, strict=True):
        if op == "/":
            if pos >= len(bits):
                return None
            out.append((step(state, op, bits[pos]), pos + 1))
        else:
            out.append((step(state, op), pos))
    return tuple(out)


def _separable(rows: tuple[_Row, ...], spec: Spec) -> bool:
    """Whether rows in identical states can still end up acceptable.

    Rows sharing a state and a remaining input evolve identically
    forever, so a distinctness spec is already lost, and an equality
    spec is lost unless those rows want the same observable.
    """
    groups: dict[tuple[State, tuple[int, ...]], list[int]] = {}
    for i, (state, pos) in enumerate(rows):
        groups.setdefault((state, spec.inputs[i][pos:]), []).append(i)
    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        if spec.distinct or len({spec.expected[i] for i in idxs}) > 1:
            return False
    return True


def search(
    spec: Spec, alphabet: tuple[str, ...], max_length: int, stats: Stats
) -> SearchResult:
    """All shortest programs over ``alphabet`` meeting ``spec``.

    Lengths are tried in increasing order; the first length with any
    hit is enumerated in full (so uniqueness claims are checkable) and
    returned.  ``length`` is ``None`` when nothing up to ``max_length``
    meets the spec.
    """
    order = order_rows(spec)
    start_rows: tuple[_Row, ...] = tuple((s, 0) for s in spec.starts)
    for length in range(max_length + 1):
        hits = _hits_at_length(spec, alphabet, length, order, stats, start_rows)
        if hits:
            return SearchResult(length, tuple(hits))
    return SearchResult(None, ())


def _hits_at_length(
    spec: Spec,
    alphabet: tuple[str, ...],
    length: int,
    order: tuple[int, ...],
    stats: Stats,
    rows: tuple[_Row, ...],
) -> list[tuple[str, ...]]:
    """Every program of exactly ``length`` meeting ``spec``."""
    hits: list[tuple[str, ...]] = []

    def rec(rows: tuple[_Row, ...], program: tuple[str, ...]) -> None:
        if len(program) == length:
            stats.candidates += 1
            finals = tuple(state for state, _ in rows)
            if _accepts(finals, spec, order, stats):
                hits.append(program)
            return
        if not _separable(rows, spec):
            return
        for op in alphabet:
            stepped = _step_rows(rows, spec, op)
            if stepped is not None:
                rec(stepped, (*program, op))

    rec(rows, ())
    return hits


# The breadth-first search below packs each row state into one base-3
# integer (A, then cells 0..2) and each frontier node into a tuple of
# them, so a node's identity is its full behaviour on every row: two
# programs reaching the same node are interchangeable, and only the
# first (shortest) is kept.

_PLACES = (1, 3, 9, 27)


def _pack(state: State) -> int:
    a, cells = state
    return a + 3 * cells[0] + 9 * cells[1] + 27 * cells[2]


def _transitions(op: str) -> tuple[int, ...]:
    """Packed-state transition table for a non-read token."""
    if op.startswith("K"):
        d = int(op[1])
        return tuple(s - s % 3 + d for s in range(81))
    cell = int(op)
    place = _PLACES[cell + 1]
    table = []
    for s in range(81):
        a = s % 3
        c = (s // place) % 3
        na = CRAZY0[a][c]
        table.append(s + (na - a) + (na - c) * place)
    return tuple(table)


def _obs_key(packed: int, observe: tuple[int, ...]) -> int:
    key = 0
    for j, cell in enumerate(observe):
        key += ((packed // _PLACES[cell + 1]) % 3) * 3**j
    return key


@dataclass(frozen=True)
class BfsResult:
    """A shortest program if found, else how deep the proof reached."""

    program: tuple[str, ...] | None
    exhausted: int
    levels: tuple[int, ...]
    capped: bool


@dataclass(frozen=True, slots=True)
class _Node:
    reads: int
    rows: tuple[int, ...]
    program: bytes = b""


def search_bfs(
    spec: Spec,
    alphabet: tuple[str, ...],
    max_depth: int,
    *,
    node_cap: int = 2_000_000,
    budget_seconds: float = 1500.0,
) -> BfsResult:
    """Breadth-first shortest-program search over packed row states.

    Serves distinctness specs whose rows share one input length.
    ``exhausted`` is the depth reached: the hit's length, or the
    deepest level fully checked without one.  ``capped`` says the
    node cap or time budget, not ``max_depth``, stopped the search.
    """
    if not spec.distinct:
        raise ValueError("the breadth-first search serves distinctness specs")
    if len({len(bits) for bits in spec.inputs}) != 1:
        raise ValueError("breadth-first rows must share one input length")
    nbits = len(spec.inputs[0])
    tables = {op: _transitions(op) for op in alphabet if op != "/"}
    # Row pairs whose remaining inputs agree at each read count: only
    # those pairs can become inseparable, so only they are checked.
    suffix_pairs = [
        tuple(
            (i, j)
            for i in range(len(spec.inputs))
            for j in range(i + 1, len(spec.inputs))
            if spec.inputs[i][r:] == spec.inputs[j][r:]
        )
        for r in range(nbits + 1)
    ]

    def accepts(rows: tuple[int, ...]) -> bool:
        return len({_obs_key(s, spec.observe) for s in rows}) == len(rows)

    start = _Node(0, tuple(_pack(s) for s in spec.starts))
    if accepts(start.rows):
        return BfsResult((), 0, (1,), capped=False)
    frontier: dict[tuple[int, tuple[int, ...]], _Node] = {
        (start.reads, start.rows): start
    }
    levels: list[int] = []
    began = time.monotonic()
    for depth in range(max_depth):
        levels.append(len(frontier))
        following: dict[tuple[int, tuple[int, ...]], _Node] = {}
        for node in frontier.values():
            for op_index, op in enumerate(alphabet):
                if op == "/":
                    if node.reads >= nbits:
                        continue
                    rows = tuple(
                        s - s % 3 + bits[node.reads]
                        for s, bits in zip(node.rows, spec.inputs, strict=True)
                    )
                    reads = node.reads + 1
                else:
                    table = tables[op]
                    rows = tuple(table[s] for s in node.rows)
                    reads = node.reads
                if any(rows[i] == rows[j] for i, j in suffix_pairs[reads]):
                    continue
                key = (reads, rows)
                if key in following:
                    continue
                program = (*node.program, op_index)
                if accepts(rows):
                    return BfsResult(
                        tuple(alphabet[k] for k in program),
                        depth + 1,
                        tuple(levels),
                        capped=False,
                    )
                following[key] = _Node(reads, rows, bytes(program))
            if len(following) > node_cap:
                return BfsResult(None, depth, tuple(levels), capped=True)
        if time.monotonic() - began > budget_seconds:
            return BfsResult(None, depth + 1, (*levels, len(following)), capped=True)
        frontier = following
    levels.append(len(frontier))
    return BfsResult(None, max_depth, tuple(levels), capped=False)
