r"""Test whether divergence really requires divergent entry positions.

``parity.py`` confirms a segment's position map ignores the tape, so rows
entering at the same position leave at the same position.  The tempting
conclusion is that rows sharing an entry share a halt verdict, making
"diverges" and "terminates" incompatible.

That argument is incomplete.  Rows re-enter the segment after a backjump,
and a row that takes an extra pass has executed a *different number* of
moves by the time it next reaches the closing ``3`` -- so its position
there can differ even though every individual map is tape-independent.  The
question is whether that second-order difference can put one row below zero
while another sits at or above it.

This measures it: run the guard and record, per row, the position at each
closing-``3`` encounter, then check whether the verdicts can ever split.
"""

import itertools

from reexec import instantiate

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine


def verdicts(template, limit=400):
    """Return per-row the sequence of closing-3 positions, or None."""
    rows = []
    code0 = instantiate(template, [0, 0])
    close_ip = len(code0) - 1
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        code = instantiate(template, bits)
        io = ScriptedIO("")
        m = _Machine(code, io)
        seen = []
        steps = 0
        try:
            while not m.halted and steps < limit:
                if m.ip == close_ip:
                    seen.append(m.pos)
                m.step()
                steps += 1
        except EOFError:
            return None
        rows.append((tuple(seen[:8]), m.halted))
    return rows


def main():
    """Look for a guard where some rows halt and others do not."""
    dips = ["1", "11", "121"]
    rights = ["2", "22", "222", "2222"]
    bodies = ["1", "11", "111", "1111", "12", "121", "1211", "112", "1121"]
    split = []
    tried = 0
    for dip, right, body in itertools.product(dips, rights, bodies):
        tpl = f"{right}{dip}3{{X0}}{body}{{X1}}3"
        tried += 1
        rows = verdicts(tpl)
        if rows is None:
            continue
        halts = [h for _, h in rows]
        if len(set(halts)) > 1:
            split.append((tpl, [s for s, _ in rows], halts))
    print(f"tried {tried} guards")
    print(f"{len(split)} have rows that split on halting\n")
    for tpl, seqs, halts in split[:8]:
        print(f"  {tpl!r:28} halts={halts}")
        for seq in seqs:
            print(f"      closing-3 positions {seq}")


if __name__ == "__main__":
    main()
