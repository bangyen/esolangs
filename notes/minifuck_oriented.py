"""Choose the print orientation instead of inheriting it.

Pinning cell 7 in the pool fix makes both print orientations available, which
adds builds (`0110` and `1101` become reachable this way).  It does not reach
`0111`: for the prototype embed the pool `0011000|0` that orientation needs is
unreachable by two clamped walks at *any* walk-out length, while `0011000|1`
is easy -- a parity constraint, not a search budget.

The column search works from the frontier (`[<[[[<` puts 0111 at cell 20),
and the endgame's orientation is decided by cell 7 -- but each alone was
tried against an endgame that inherited the other.  Do both: search the
column from the frontier, then run an endgame that pins cell 7 to each
orientation in turn.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import minifuck_boolean_prototype as gen
from minifuck_column import find_column
from minifuck_shelf import BASE, embed


def pool_fix_oriented(j, walk_out, cell7):
    """Like `pool_fix`, but pin cell 7 too, so the print orientation is chosen."""
    target = [0, 0, 1, 1, 0, 0, 0, cell7]
    for a in range(11):
        for b in range(11):
            probe = gen.Joint(j.n)
            probe.parts = list(j.parts)
            probe.ms = [m.copy() for m in j.ms]
            for k in (a, b):
                probe.emit("[x" * k)
                gen.clamp(probe)
            try:
                gen.walk_to(probe, walk_out)
            except AssertionError:
                continue
            if [probe.col(c)[0] for c in range(8)] == target:
                for k in (a, b):
                    j.emit("[x" * k)
                    gen.clamp(j)
                return
    raise ValueError("no oriented pool pattern")


def endgame_oriented(j, acc, cell7):
    """Run the endgame with the print orientation chosen, not inherited."""
    pool_fix_oriented(j, acc - 1, cell7)
    gen.walk_to(j, acc - 1)
    live = j.col(acc)
    j.emit("[<")
    if j.ptrs() != tuple(acc - 1 + v for v in live):
        raise ValueError("read did not diverge as expected")
    j.emit("<" * (acc - 7))
    for cell in range(8):
        if len(set(j.col(cell))) != 1:
            raise ValueError(f"pool cell {cell} input-dependent")
    j.emit("[x.")


def build(table, depth=13):
    """Emit a template for `table` using both fixes together."""
    want = [int(c) for c in table]
    for park in range(BASE - 2, BASE + 8):
        base = embed(2)
        gen.clamp(base)
        try:
            gen.walk_to(base, park)
        except AssertionError:
            continue
        hit = find_column(base, want, maxlen=depth, window=40)
        if not hit:
            continue
        code, _cell, _comp = hit
        base.emit(code)
        gen.clamp(base)
        for cell7 in (0, 1):
            for acc in range(9, 34):
                probe = gen.Joint(2)
                probe.parts = list(base.parts)
                probe.ms = [m.copy() for m in base.ms]
                try:
                    endgame_oriented(probe, acc, cell7)
                except (ValueError, AssertionError):
                    continue
                if ["".join(m.out) for m in probe.ms] == list(table):
                    return probe
    raise ValueError(f"no build for {table!r}")


if __name__ == "__main__":
    import time

    for table in ("0111", "1000", "0110", "1101"):
        t0 = time.time()
        try:
            j = build(table)
            print(f"{table}: OK len={len(j.template())}  ({time.time() - t0:.0f}s)")
        except ValueError as exc:
            print(f"{table}: {exc}  ({time.time() - t0:.0f}s)")
