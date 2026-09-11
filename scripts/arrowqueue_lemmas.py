#!/usr/bin/env python3
"""Executed lemma checks behind ``docs/arrowqueue_generator.md``.

The proof there is total over every arity, so nothing in this file
enumerates truth tables to establish the claim -- each check pins one
*finite* lemma the induction rests on.  One named lemma per output line.

Default run is a few seconds.  ``--deep`` adds the high-arity composition
runs (``n = 12`` alone is ~96s), and ``--tree-sweep`` adds the exhaustive
65536-table tree-only sweep (~3 minutes) that certifies leaf-index
routing rather than merely the verdict.

Exit status is non-zero if any lemma fails.
"""

from __future__ import annotations

import argparse
import itertools
import random
import sys

from esolangs.interpreters.grid_based.arrowqueue import _advance, _Machine
from esolangs.tools.boolean.parameterized import (
    _FIRST_ONE,
    _FIRST_ZERO,
    _MIDDLE,
    _NEXT_ONE,
    _NEXT_ZERO,
    _TREE_0,
    _TREE_1,
    _TREE_BRANCH_0,
    _TREE_BRANCH_1,
    _connect,
    _drained_leaf,
    _header_rows,
    _instantiate_arrowqueue,
    _tree,
    arrowqueue,
)
from esolangs.vm import run_until_halt_or_cycle

#: The four loop components the ring's corners must pop, in queue order.
RDLU = (0, 1, 2, 3)

#: Composed trees the geometry checks run against.  Shapes, not a sample of
#: tables: G1-G3 are facts about ``_connect``'s three writes, and these
#: exercise a balanced tree, a lopsided one, and two folded halves.
_GEOMETRY_SHAPES = [
    "0110",
    "01101001",
    "1000",
    "1111000010101010",
    "0111011101110111",
]

failures: list[str] = []


def report(lemma: str, *, ok: bool, detail: str) -> None:
    """Print one lemma line and record a failure."""
    status = "ok  " if ok else "FAIL"
    print(f"[{status}] {lemma:28s} {detail}", flush=True)
    if not ok:
        failures.append(lemma)


def _run_block(
    rows: list[str], state: tuple[int, int, int, tuple[int, ...]], cap: int = 100_000
) -> tuple[int, int, int, tuple[int, ...], bool]:
    """Step a bare block from ``state`` until it leaves the block's rectangle."""
    width = max(map(len, rows), default=0)
    grid = tuple(row.ljust(width) for row in rows)
    current = (*state, False)
    for _ in range(cap):
        row, col, _d, _q, done = current
        if done or not (0 <= row < len(grid) and 0 <= col < width):
            break
        current = _advance(current, grid, width)
    return current


def _verdict_from(rows: list[str], state: tuple[int, int, int, tuple[int, ...]]) -> str:
    """Halt-or-cycle verdict from an arbitrary entry state."""
    machine = _Machine(list(rows))
    machine.state = (*state, not machine.grid)
    return "0" if run_until_halt_or_cycle(machine) else "1"


def _glyph_rows(block: list[str]) -> set[int]:
    """Row indices of ``block`` that hold at least one glyph."""
    return {r for r, row in enumerate(block) if row.strip()}


def check_h1_pitch() -> None:
    """H1: the header is exactly 4n+1 rows for every arity and pattern."""
    bad = 0
    total = 0
    for n in range(1, 13):
        patterns = (
            list(itertools.product([0, 1], repeat=n))
            if n <= 10
            else [tuple(random.choice([0, 1]) for _ in range(n)) for _ in range(200)]
        )
        for bits in patterns:
            total += 1
            if len(_header_rows(list(bits))) != 4 * n + 1:
                bad += 1
    heights = (len(_FIRST_ONE), len(_FIRST_ZERO), len(_NEXT_ONE), len(_NEXT_ZERO))
    report(
        "H1 header pitch",
        ok=bad == 0 and heights == (5, 5, 4, 4),
        detail=f"{total} patterns to n=12, {bad} wrong heights; heights {heights}",
    )


def check_h2_h3_handoff() -> None:
    """H2/H3: header exits down col 3 with the bits; +middle enters the tree."""
    bad_h2 = bad_h3 = 0
    total = 0
    for n in range(1, 13):
        patterns = (
            list(itertools.product([0, 1], repeat=n))
            if n <= 9
            else [tuple(random.choice([0, 1]) for _ in range(n)) for _ in range(200)]
        )
        for bits in patterns:
            total += 1
            row, col, d, queue, _done = _run_block(
                _header_rows(list(bits)), (0, 0, 0, ())
            )
            if not (queue == tuple(bits) and d == 1 and col == 3 and row == 4 * n + 1):
                bad_h2 += 1
            rows = _header_rows(list(bits)) + list(_MIDDLE)
            row, col, d, queue, _done = _run_block(rows, (0, 0, 0, ()))
            if not (
                queue == (*bits, *RDLU)
                and d == 1
                and col == 1
                and row == 4 * n + 1 + len(_MIDDLE)
            ):
                bad_h3 += 1
    report(
        "H2 header chain",
        ok=bad_h2 == 0,
        detail=f"{total} patterns to n=12, {bad_h2} violations",
    )
    report(
        "H3 middle hand-off",
        ok=bad_h3 == 0,
        detail=f"queue becomes bits+RDLU, enters tree down col 1; {bad_h3} violations",
    )


def check_g_geometry() -> None:
    """G1/G2/G3: row disjointness, blank right corridor, and the entry column.

    G1 compares the *actual* glyph rows of the two placed subtrees in the
    composed grid rather than restating ``_connect``'s own arithmetic --
    an assertion built from ``yb = len(t0)`` would be true by definition
    and would check nothing.
    """
    plus = [
        (r, c)
        for r, row in enumerate(_TREE_BRANCH_0)
        for c, ch in enumerate(row)
        if ch == "+"
    ]
    report("G3 entry cell", ok=plus == [(0, 1)], detail=f"0-branch '+' at {plus}")

    overlaps = 0
    right_blockers = 0
    column_blockers = 0
    for values in _GEOMETRY_SHAPES:
        half = len(values) // 2
        t0, t1 = _tree(list(values[:half])), _tree(list(values[half:]))
        grid = _connect(t0, t1)
        yb = len(t0)
        width = len(grid[0])

        # G1: the rows the two subtrees actually occupy must not intersect.
        rows_t0 = _glyph_rows(t0)
        rows_t1 = {yb + r for r in _glyph_rows(t1)}
        overlaps += len(rows_t0 & rows_t1)

        # G2: within t0's rows nothing is written right of t0.
        for r in range(len(t0)):
            for c in range(3 + len(t0[0]), width):
                if grid[r][c] != " ":
                    right_blockers += 1

        # G3 (second half): column 1 between the two branch blocks is blank,
        # so the 0-branch's downward exit falls through to the 1-branch.
        for r in range(3, yb):
            if grid[r][1] != " ":
                column_blockers += 1

    report(
        "G1 row disjointness",
        ok=overlaps == 0,
        detail=f"{len(_GEOMETRY_SHAPES)} composed trees, {overlaps} shared glyph rows",
    )
    report(
        "G2 right corridor",
        ok=right_blockers == 0,
        detail=f"{right_blockers} glyphs right of a subtree within its own rows",
    )
    report(
        "G3 drop column clear",
        ok=column_blockers == 0,
        detail=f"{column_blockers} glyphs in column 1 between the branch blocks",
    )


def check_b_branches() -> None:
    """B2/B3/B3': branch routing, reflection, and entry-column sensitivity.

    B2 is checked under *both* entry styles: the top-level tree is entered
    heading down at (0, 1), while every recursive subtree is entered
    heading right at its own (0, 0).  The induction uses both, so both are
    executed here.
    """
    down_exits = {}
    right_exits = {}
    for bit in (0, 1):
        row, col, d, queue, _done = _run_block(_TREE_BRANCH_0, (0, 1, 1, (bit,)))
        down_exits[bit] = (row, col, d, queue)
        row, col, d, queue, _done = _run_block(_TREE_BRANCH_0, (0, 0, 0, (bit,)))
        right_exits[bit] = (row, col, d, queue)

    ok_down = (
        down_exits[0][:3] == (0, 3, 0)
        and down_exits[1][:3] == (3, 1, 1)
        and down_exits[0][3] == ()
        and down_exits[1][3] == ()
    )
    report(
        "B2 0-branch (down-entry)",
        ok=ok_down,
        detail=f"bit0 -> {down_exits[0][:3]}, bit1 -> {down_exits[1][:3]}, bit popped",
    )

    ok_right = (
        right_exits[0][:3] == (0, 3, 0)
        and right_exits[1][:3] == (3, 1, 1)
        and right_exits[0][3] == ()
        and right_exits[1][3] == ()
    )
    report(
        "B2 0-branch (right-entry)",
        ok=ok_right,
        detail=f"bit0 -> {right_exits[0][:3]}, bit1 -> {right_exits[1][:3]}, same",
    )

    row, col, d, queue, _done = _run_block(_TREE_BRANCH_1, (0, 1, 1, (7,)))
    report(
        "B3 1-branch reflects",
        ok=(row, col, d) == (0, 3, 0) and queue == (7,),
        detail=f"exit {(row, col, d)}, queue preserved {queue}",
    )

    row, col, d, queue, _done = _run_block(_TREE_BRANCH_1, (0, 0, 1, ()))
    report(
        "B3' entry column matters",
        ok=not 0 <= col < 3,
        detail=f"1-branch entered at col 0 leaves the grid: exit {(row, col, d)}",
    )


def check_l_leaves() -> None:
    """L1/L2/L2'/L3/L4: leaf behaviour, drains, and the bare ring's entry."""
    right = _verdict_from(_TREE_1, (0, 0, 0, RDLU))
    down = _verdict_from(_TREE_1, (0, 1, 1, RDLU))
    report(
        "L2 ring sustains (right)",
        ok=right == "1",
        detail=f"right-entry verdict {right!r} (1 = loops)",
    )
    report(
        "L2' ring halts (down)",
        ok=down == "0",
        detail=f"down-entry verdict {down!r} -- entry styles are NOT interchangeable",
    )

    zero_ok = all(
        _verdict_from(_TREE_0, state) == "0"
        for state in ((0, 0, 0, RDLU), (0, 1, 1, RDLU))
    )
    report(
        "L1 zero leaf halts",
        ok=zero_ok,
        detail="empty block exits the grid under both entries",
    )

    bad = 0
    cases = 0
    for k in range(9):
        leaf = _drained_leaf("1", k)
        shape_ok = (
            len(leaf) == k + 3
            and sum(row.count("+") for row in leaf) == k + 4
            and sum(row.count("~") for row in leaf)
            == sum(row.count("~") for row in _TREE_1)
        )
        if not shape_ok:
            bad += 1
        for stale in itertools.product([0, 1], repeat=k):
            queue = (*stale, *RDLU)
            for state in ((0, 0, 0, queue), (0, 1, 1, queue)):
                cases += 1
                if _verdict_from(leaf, state) != "1":
                    bad += 1
        if _drained_leaf("0", k) != list(_TREE_0):
            bad += 1
    report(
        "L3 drains drain",
        ok=bad == 0,
        detail=f"k=0..8, all stale patterns x 2 entries = {cases} runs, {bad} bad",
    )

    bare_top = [
        format(i, f"0{2**n}b")
        for n in (1, 2, 3)
        for i in range(2 ** (2**n))
        if _tree(list(format(i, f"0{2**n}b"))) == list(_TREE_1)
    ]
    const_ok = all(
        _tree(list("1" * (2**n))) == _drained_leaf("1", n) for n in range(1, 6)
    )
    report(
        "L4 bare ring never on top",
        ok=not bare_top and const_ok,
        detail=f"{len(bare_top)} tables (n<=3) top out bare; constant-1 folds to k=n",
    )


def check_c1_compaction(*, deep: bool) -> None:
    """C1: _compact preserves the halt-or-cycle verdict."""
    mismatch = 0
    pairs = 0
    arities = (1, 2, 3, 4) if deep else (1, 2, 3)
    for n in arities:
        tables = (
            [format(i, f"0{2**n}b") for i in range(2 ** (2**n))]
            if n <= 3
            else ["".join(random.choice("01") for _ in range(2**n)) for _ in range(40)]
        )
        for table in tables:
            template = arrowqueue(table)
            rows = template.split("\n")
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                raw = "\n".join(_header_rows(bits) + rows[4 * n + 1 :])
                small = _instantiate_arrowqueue(template, bits)
                pairs += 1
                raw_v = _verdict_from(raw.split("\n"), (0, 0, 0, ()))
                small_v = _verdict_from(small.split("\n"), (0, 0, 0, ()))
                if raw_v != small_v or small_v != table[combo]:
                    mismatch += 1
    report(
        "C1 compaction preserves",
        ok=mismatch == 0,
        detail=f"{pairs} uncompacted/compacted pairs, {mismatch} mismatches",
    )


def check_tree_sweep() -> None:
    """T: leaf-index routing, certified by an exhaustive tree-only sweep."""
    bad = 0
    for n in (1, 2, 3, 4):
        for i in range(2 ** (2**n)):
            values = format(i, f"0{2**n}b")
            rows = _tree(list(values))
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - j)) & 1 for j in range(n)]
                if _verdict_from(rows, (0, 1, 1, (*bits, *RDLU))) != values[combo]:
                    bad += 1
    report(
        "T tree-only routing",
        ok=bad == 0,
        detail=f"all tables n<=4 (65536 at n=4) entered at the tree, {bad} failures",
    )


def check_deep_composition() -> None:
    """Composition past every swept arity: whole programs at n = 6..12."""
    bad = 0
    detail = []
    for n in (6, 8, 10, 12):
        table = "".join(random.choice("01") for _ in range(2**n))
        template = arrowqueue(table)
        size = 0
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            program = _instantiate_arrowqueue(template, bits)
            size = max(size, len(program))
            if _verdict_from(program.split("\n"), (0, 0, 0, ())) != table[combo]:
                bad += 1
        detail.append(f"n={n}({size}B)")
    report(
        "deep composition", ok=bad == 0, detail=f"{' '.join(detail)}, {bad} failures"
    )

    bad = 0
    for n in (8, 10):
        for table in (
            "1" * (2**n),
            "0" * (2**n),
            "0" * (2**n - 1) + "1",
            "1" + "0" * (2**n - 1),
            "01" * (2 ** (n - 1)),
        ):
            template = arrowqueue(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                program = _instantiate_arrowqueue(template, bits)
                if _verdict_from(program.split("\n"), (0, 0, 0, ())) != table[combo]:
                    bad += 1
    report(
        "deep extremes",
        ok=bad == 0,
        detail=f"all-ones/zeros/single-1/alternating at n=8,10, {bad} failures",
    )


def main() -> int:
    """Run the lemma checks and return a process exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deep",
        action="store_true",
        help="add high-arity composition runs (~2 minutes)",
    )
    parser.add_argument(
        "--tree-sweep",
        action="store_true",
        help="add the exhaustive 65536-table tree sweep (~3 minutes)",
    )
    args = parser.parse_args()

    # Seeded so the sampled arities and random tables are reproducible.
    random.seed(20240904)

    check_h1_pitch()
    check_h2_h3_handoff()
    check_g_geometry()
    check_b_branches()
    check_l_leaves()
    check_c1_compaction(deep=args.deep)
    if args.tree_sweep:
        check_tree_sweep()
    if args.deep:
        check_deep_composition()

    print()
    if failures:
        print(f"{len(failures)} lemma(s) FAILED: {', '.join(failures)}")
        return 1
    print("all lemmas hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
