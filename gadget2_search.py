"""Find a re-zero gadget for the SECOND read, from the real frontier.

GADGET was found by a BFS from the blank-tape post-read state.  After bit 1
is banked the tape is populated, so the same string no longer re-zeroes the
pool -- cell 7 stays input-dependent, and _endgame rejects every accumulator.

This searches from the ACTUAL post-second-read joint state (all 2**n rows in
lockstep), requiring: pool all-zero (hence input-independent), pointers equal,
no output, and the rows still distinct past the pool.
"""
import sys
import importlib
from collections import deque
sys.path.insert(0, "src")
M = importlib.import_module("esolangs.tools.boolean.minifuck")
from reading_gen2 import _ReadSim, _advance  # noqa: E402

READ = "[<."
GADGET = "[[[<[[[[[[[[[[[<<<[<[[[<"
SPLIT = "<[<"


def frontier(n=2):
    """Joint state right after the second read (bit 1 already banked)."""
    rows = [[(r >> (n - 1 - k)) & 1 for k in range(n)] for r in range(2**n)]
    sims = [_ReadSim(512, feed=row) for row in rows]
    for sim, row in zip(sims, rows):
        _advance(sim, READ + GADGET + SPLIT, row[0])
        _advance(sim, READ, row[1])
    return sims, rows


def key(sims):
    return tuple((tuple(s.tape[:40]), s.ptr, s.skip) for s in sims)


def search(max_depth=26):
    sims, _rows = frontier()
    seen = {key(sims)}
    dq = deque([(sims, "")])
    while dq:
        cur, path = dq.popleft()
        if len(path) >= max_depth:
            continue
        for ins in "[<":
            nxt = [s.copy() for s in cur]
            for s in nxt:
                _advance(s, ins, 0)          # no read fires here
            if any(s.out for s in nxt):      # junk output disqualifies
                continue
            newpath = path + ins
            pool_ok = all(not any(s.tape[:8]) for s in nxt)
            ptr_ok = len({s.ptr for s in nxt}) == 1
            distinct = len({tuple(s.tape[8:40]) for s in nxt}) == len(nxt)
            if pool_ok and ptr_ok and distinct:
                return newpath, nxt
            k = key(nxt)
            if k not in seen:
                seen.add(k)
                dq.append((nxt, newpath))
    return None, None


path, res = search()
print("second-read gadget:", repr(path))
if res:
    for s in res:
        print(f"   ptr={s.ptr} pool={s.tape[:8]} cells8-14={s.tape[8:14]}")
