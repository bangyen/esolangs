"""Record which pool patterns are reachable, and by how many walks.

Settles why `0111` does not build: for the prototype embed the pool
`0011000|0` is unreachable by two clamped walks at every walk-out length
tried, while `0011000|1` is easy.  That parity is exactly the difference
between a table and its complement at the print stage.

`pool_fix` tries two clamped `[x`-walks.  That is enough for the pattern
`0011000|1` at walk-out 19 but not for `0011000|0`, which is the whole reason
`0111` does not build while its complement does.  The pool is
input-independent, so this is a small deterministic search: sweep walk counts
and lengths and record what is reachable.
"""

import pathlib
import sys
from itertools import product

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import minifuck_boolean_prototype as gen
from minifuck_shelf import embed


def reachable(j, walk_out, walks, span=11):
    """Pool patterns reachable by `walks` clamped [x-walks, keyed to the code."""
    found = {}
    for lengths in product(range(span), repeat=walks):
        probe = gen.Joint(j.n)
        probe.parts = list(j.parts)
        probe.ms = [m.copy() for m in j.ms]
        for k in lengths:
            probe.emit("[x" * k)
            gen.clamp(probe)
        try:
            gen.walk_to(probe, walk_out)
        except AssertionError:
            continue
        pool = tuple(probe.col(c)[0] for c in range(8))
        found.setdefault(pool, lengths)
    return found


if __name__ == "__main__":
    j = embed(2)
    gen.clamp(j)
    want1 = (0, 0, 1, 1, 0, 0, 0, 1)
    want0 = (0, 0, 1, 1, 0, 0, 0, 0)
    for walks in (2, 3):
        got = reachable(j, 19, walks)
        print(f"{walks} walks: {len(got)} distinct pools")
        print(f"   0011000|1 -> {got.get(want1)}")
        print(f"   0011000|0 -> {got.get(want0)}")
