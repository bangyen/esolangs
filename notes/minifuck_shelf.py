"""Non-destructive reads and the literal shelf.

The minterm loop stalled because banking a literal destroyed it: `[<`
consumes the cell it reads, and the walk out rewrites the region it crosses,
so a column tested for one row was gone before the next row needed it.

Two things fix that, and both are established here:

* **Reads need not be destructive.**  A gadget exists that diverges the
  pointer by a cell's value and leaves the cell standing.  `[<<[[<` does it
  on a blank tape, but its precondition (both neighbours zero) belongs to
  *that* gadget, not to the problem -- so :func:`find_read` searches for one
  from the live joint state instead, with whatever junk is present as part of
  the starting condition.  It finds reads in well under a second.
* **The shelf is as wide as the emitter wants.**  Literals are banked out of
  the dense region onto spaced ground, and re-banking an entry delivers its
  complement -- the second polarity the one-sided ``== 0`` tests need.  With
  two or three rounds of that, every row is separable by a conjunction of
  ``== 0`` tests at ``n == 2, 3, 4`` (4/4, 8/8, 16/16).

What is *not* solved here is executing a plan: chaining the reads means
holding divergence across steps, and clamping between them to keep the rows
in step discards the very divergence being accumulated.  See the notes.
"""

import pathlib
import sys
from collections import deque

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import minifuck_boolean_prototype as gen

BASE = 16
SEP = "[x<[x"
STRIDE = 4  # gap between banked literals


def embed(n, passes=2):
    """Embed the inputs and settle the region; pointer converged at BASE-1."""
    j = gen.Joint(n)
    gen.walk_to(j, BASE - 1)
    for i in range(n):
        j.emit_setter(i)
        j.emit("[x")
        if i + 1 < n:
            j.emit(SEP)
    for _ in range(passes):
        gen.clamp(j)
        gen.walk_to(j, BASE - 1)
    return j


def high_water(j):
    """Rightmost cell any row has written."""
    top = 0
    for m in j.ms:
        for i in range(len(m.tape) - 1, -1, -1):
            if m.tape[i]:
                top = max(top, i)
                break
    return top


def bank(j, cell, landing):
    """Relay `cell` to `landing` (a destructive read) and clamp.

    Returns the column actually delivered: the walk's row-dependent carry
    decides whether the value or its complement arrives, so the caller reads
    the result rather than predicting it.
    """
    gen.walk_to(j, cell - 1)
    j.emit("[<")
    pad = landing - (cell - 1) - 1
    if pad < 0:
        raise ValueError(f"landing {landing} is behind cell {cell}")
    j.emit("[x" * pad)
    j.emit("[x")
    col = j.col(landing)
    gen.clamp(j)
    return col


def find_read(j, cell, entry, maxlen=13):
    """Search the live joint state for a non-destructive read of `cell`.

    Accepts code whose exit pointer offsets equal `cell`'s column and which
    leaves the cell's value untouched in every row.  Returns None if no such
    code exists within `maxlen`.
    """
    want = j.col(cell)
    if len(set(want)) < 2:
        return None  # a constant column carries nothing to read
    probe = gen.Joint(j.n)
    probe.parts = list(j.parts)
    probe.ms = [m.copy() for m in j.ms]
    gen.walk_to(probe, entry)

    root = tuple(m.copy() for m in probe.ms)
    keep = [m.tape[cell] for m in root]
    seen = {tuple(m.key() for m in root)}
    q = deque([(root, "")])
    while q:
        states, prog = q.popleft()
        if len(prog) >= maxlen:
            continue
        for ch in "<[x":
            new = []
            for m in states:
                c = m.copy()
                c.exec(ch)
                new.append(c)
            if any(m.dead for m in new):
                continue
            k = tuple(m.key() for m in new)
            if k in seen:
                continue
            seen.add(k)
            p = prog + ch
            if not any(m.skip for m in new):
                lo = min(m.ptr for m in new)
                offs = tuple(m.ptr - lo for m in new)
                intact = all(m.tape[cell] == v for m, v in zip(new, keep, strict=True))
                if offs == want and intact:
                    return p
            q.append((tuple(new), p))
    return None


def build_shelf(j, width=None, rounds=3):
    """Bank the region's columns onto spaced ground, then re-bank for more.

    Re-banking delivers complements, so extra rounds widen the set of columns
    available to the conjunction rather than repeating it.
    """
    width = width or 4 * j.n + 6
    shelf = {}
    for cell in [c for c in range(BASE, BASE + width) if len(set(j.col(c))) > 1]:
        landing = high_water(j) + STRIDE
        col = bank(j, cell, landing)
        if len(set(col)) > 1:
            shelf[landing] = col
    for _ in range(rounds - 1):
        for cell in sorted(shelf):
            landing = high_water(j) + STRIDE
            col = bank(j, cell, landing)
            if len(set(col)) > 1 and col not in shelf.values():
                shelf[landing] = col
    return shelf


def plan_conjunction(shelf, row):
    """Shelf cells whose ``== 0`` tests select exactly `row`, or None."""
    width = len(next(iter(shelf.values())))
    tested, surviving = [], list(range(width))
    for cell in sorted(shelf):
        if surviving == [row]:
            break
        if shelf[cell][row] != 0:
            continue
        sel = [r for r in surviving if shelf[cell][r] == 0]
        if len(sel) < len(surviving):
            tested.append(cell)
            surviving = sel
    return tested if surviving == [row] else None


if __name__ == "__main__":
    for n in (2, 3, 4):
        j = embed(n)
        shelf = build_shelf(j)
        ok = sum(plan_conjunction(shelf, r) is not None for r in range(2**n))
        reads = sum(
            find_read(j, c, entry=e) is not None
            for c in sorted(shelf)[:4]
            for e in (c - 2,)
        )
        print(
            f"n={n}: shelf {len(shelf)} entries, {ok}/{2**n} rows separable, "
            f"{reads}/4 sampled cells have a live non-destructive read"
        )
