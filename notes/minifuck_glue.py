"""Glue the parked search to the endgame by execution.

Generates 14 of the 16 two-input tables (~5 minutes); `0111` and `1000`
resist this route, though `1000` builds through the direct scan in
minifuck_boolean_prototype, so the two routes are complementary.

The two stages could not be sequenced by reasoning about the pool, so glue
them by running the endgame in a copy for every candidate cell and accepting
whichever actually prints the table.  The parked search supplies several
candidates, which is the degree of freedom a single-candidate version lacked.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import minifuck_boolean_prototype as gen
from minifuck_parked_search import find_parked
from minifuck_shelf import embed


def build(table, depth=15, limit=12):
    """Emit a template printing `table`, or raise."""
    n = (len(table) - 1).bit_length()
    want = [int(c) for c in table]
    for code, _cell, _comp in find_parked(embed(n), want, maxlen=depth, limit=limit):
        base = embed(n)
        base.emit(code)
        gen.clamp(base)
        top = max(max(m.ptr for m in base.ms) for _ in (0,)) + 2
        for cell in range(9, max(top, 30)):
            probe = gen.Joint(n)
            probe.parts = list(base.parts)
            probe.ms = [m.copy() for m in base.ms]
            try:
                gen.endgame(probe, cell)
            except (ValueError, AssertionError):
                continue
            if ["".join(m.out) for m in probe.ms] == list(table):
                gen.endgame(base, cell)
                return base
    raise ValueError(f"no candidate printed {table!r}")


if __name__ == "__main__":
    import time

    ok, misses = 0, []
    t0 = time.time()
    for t in range(16):
        table = f"{t:04b}"
        try:
            j = build(table)
            ok += 1
            print(f"  {table}: OK len={len(j.template())}")
        except ValueError:
            misses.append(table)
            print(f"  {table}: no build")
    print(f"n=2: {ok}/16 generated ({time.time() - t0:.0f}s)")
