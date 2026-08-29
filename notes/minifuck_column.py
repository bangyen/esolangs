"""Target-column search, and why a "clean" bank was the wrong goal.

Three attempts to bank a literal cleanly all failed the same way: whatever
route was taken, the delivered column came out a function of the literal
*and* the path.  That is not a defect to engineer around -- it is the only
source of non-linearity in the language.  A bank that delivered exactly the
literal every time could only ever move existing columns about, and the
columns reachable that way are closed under XOR and complement, so no
conjunction would ever appear.

The row-dependent absorption does the multiplexing instead: while the
pointer is diverged, which cells a walk crosses depends on the row, so what
gets XORed in depends on the row.  The evidence that this escapes the affine
trap is direct -- 3/9 shelf columns at ``n == 2`` and 22/26 at ``n == 3`` are
**not** affine functions of the inputs (see :func:`nonaffine`), and one of
them at ``n == 2`` is plain AND.

So the emitter should not chase a gadget that preserves meaning; it should
chase a *result*.  :func:`find_column` searches the live joint state for code
after which some cell holds the wanted column, and it reaches **all 16
tables at n == 2 in about a second** from the embed alone.

What is still missing is the hand-off: the search leaves the pointer wherever
it finished, and walking back to the answer cell re-crosses (and so changes)
it.  Folding the read into the search's acceptance -- demanding a state where
the pointer is *already* parked to read the answer -- is the next step.
"""

import pathlib
import sys
from collections import deque

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from minifuck_shelf import build_shelf, embed


def find_column(j, target, maxlen=12, window=None):
    """Find code after which some cell holds `target` (or its complement).

    Returns ``(code, cell, complemented)`` or None.  The search runs from the
    live joint state, so whatever the tape already holds is part of the
    starting condition rather than a precondition to establish.
    """
    want = tuple(target)
    comp = tuple(1 - v for v in want)
    root = tuple(m.copy() for m in j.ms)
    hi = 0
    for m in root:
        for i in range(len(m.tape) - 1, -1, -1):
            if m.tape[i]:
                hi = max(hi, i)
                break
    top = window or hi + 3

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
                for cell in range(1, top):
                    col = tuple(m.tape[cell] for m in new)
                    if col == want:
                        return p, cell, False
                    if col == comp:
                        return p, cell, True
            q.append((tuple(new), p))
    return None


def affine_span(n):
    """Every column that is an affine (XOR/complement) function of the inputs."""
    rows = [[(r >> (n - 1 - k)) & 1 for k in range(n)] for r in range(2**n)]
    span = set()
    for mask in range(2**n):
        for const in (0, 1):
            span.add(
                tuple(
                    const ^ sum(b for i, b in enumerate(bits) if mask >> i & 1) % 2
                    for bits in rows
                )
            )
    return span


def nonaffine(shelf, n):
    """Shelf entries whose column is not an affine function of the inputs."""
    span = affine_span(n)
    return {cell: col for cell, col in shelf.items() if col not in span}


if __name__ == "__main__":
    import time

    for n in (2, 3):
        j = embed(n)
        shelf = build_shelf(j)
        odd = nonaffine(shelf, n)
        print(f"n={n}: {len(odd)}/{len(shelf)} shelf columns are non-affine")

    t0 = time.time()
    reached = 0
    for t in range(16):
        table = f"{t:04b}"
        probe = embed(2)
        if find_column(probe, [int(c) for c in table], maxlen=11):
            reached += 1
    print(f"n=2: {reached}/16 tables reachable as a column ({time.time() - t0:.0f}s)")
