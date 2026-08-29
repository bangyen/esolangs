"""Combine the two routes: direct scan, then the parked search.

Together they generate 15 of the 16 two-input tables (~5.5 minutes); only
`0111` (OR) resists both.

They cover different tables -- `1000` builds through the original
direct-scan prototype but not through the parked route, and most of the rest
the other way round -- so try the cheap one first and fall back.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import minifuck_boolean_prototype as proto
from minifuck_glue import build as parked_build


def build(table):
    """Emit a verified template for `table` by whichever route works."""
    try:
        return proto.emit_program(table)
    except (ValueError, AssertionError):
        pass
    return parked_build(table).template()


if __name__ == "__main__":
    import time

    ok, misses = 0, []
    t0 = time.time()
    for t in range(16):
        table = f"{t:04b}"
        try:
            tmpl = build(table)
            ok += 1
            print(f"  {table}: OK len={len(tmpl)}")
        except (ValueError, AssertionError):
            misses.append(table)
            print(f"  {table}: no build")
    print(f"n=2: {ok}/16 ({time.time() - t0:.0f}s), misses {misses}")
