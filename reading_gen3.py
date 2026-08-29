"""Reading prologue with a per-read gadget found from the real frontier.

GADGET (blank-tape) re-zeroes only the FIRST read.  After bit 1 is banked the
tape is populated, so the second read needs its own gadget, searched from the
actual post-second-read joint state.  This composes them and leaves the pool
input-independent, which is what _endgame requires.
"""
import sys
import importlib
sys.path.insert(0, "src")
M = importlib.import_module("esolangs.tools.boolean.minifuck")
from reading_gen2 import _ReadSim, _advance  # noqa: E402

READ = "[<."
GADGET1 = "[[[<[[[[[[[[[[[<<<[<[[[<"
SPLIT = "<[<"
GADGET2 = "<[[<<<[<<[<[<<<<<<<["


def reading_joint(n, size=512):
    """Rows advanced by reads; pool left input-independent at the end."""
    j = M._Joint(n, size=size)
    j.ms = [_ReadSim(size, feed=row) for row in j.rows]

    def run(code, idx):
        for sim, row in zip(j.ms, j.rows):
            _advance(sim, code, row[idx])
        j.parts.append(code)

    run(READ + GADGET1 + SPLIT, 0)
    for i in range(1, n):
        run(READ, i)
        run(GADGET2, i)
    return j


if __name__ == "__main__":
    for n in (1, 2):
        j = reading_joint(n)
        M._clamp(j)
        bad = [c for c in range(8) if len(set(j.col(c))) != 1]
        states = {(tuple(m.tape), m.ptr) for m in j.ms}
        outs = {"".join(m.out) for m in j.ms}
        print(f"n={n}: pool-dependent={bad} distinct={len(states)}/{len(j.ms)} outputs={outs}")
