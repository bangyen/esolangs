"""Search for a state that is ready to read the answer.

Reaches all 16 tables at n == 2 (depth <= 15), which is what the plain
find_column could not do: parking is part of the acceptance, so no walk
intervenes between producing the answer column and reading it.

The gap was the hand-off: find_column leaves the pointer wherever it
finished, and walking back to the answer cell re-crosses it.  So make the
parking part of what is searched for -- accept only states where some cell
holds the target column *and* the pointer sits immediately left of it,
converged.  Then `[<` reads it with no intervening walk.
"""

import pathlib
import sys
from collections import deque

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from minifuck_shelf import embed


def find_parked(j, target, maxlen=12, window=40, limit=1):
    """Find code leaving `target` in a cell with the pointer parked to read it."""
    want = tuple(target)
    comp = tuple(1 - v for v in want)
    root = tuple(m.copy() for m in j.ms)
    hits: list[tuple[str, int, bool]] = []
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
                ptrs = {m.ptr for m in new}
                if len(ptrs) == 1:
                    cell = ptrs.pop() + 1
                    if cell < window:
                        col = tuple(m.tape[cell] for m in new)
                        if col in (want, comp):
                            hits.append((p, cell, col == comp))
                            if len(hits) >= limit:
                                return hits
            q.append((tuple(new), p))
    return hits


if __name__ == "__main__":
    import time

    ok = 0
    t0 = time.time()
    for t in range(16):
        table = f"{t:04b}"
        hit = None
        for depth in (11, 13, 15):
            hit = find_parked(embed(2), [int(c) for c in table], maxlen=depth)
            if hit:
                break
        ok += hit is not None
    print(
        f"n=2: {ok}/16 tables reach a parked-to-read state "
        f"(depth <= 15, {time.time() - t0:.0f}s)"
    )
