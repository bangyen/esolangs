r"""Report which cell the closing 3 tests on each pass, and why loops persist.

``bounded.py`` finds none of 640 layouts with small, differing, halting pass
counts.  The loop exits only if the re-run *clears* the guard cell, so this
checks the mechanism directly: does the segment flip the cell that the
closing ``3`` tests?

The complication is that the closing ``3`` tests whatever is under the
pointer *at that moment*, and the segment moves the pointer.  If the pointer
returns to the same cell each pass and the segment flips it an odd number of
times, the guard alternates TRUE/FALSE and the loop runs exactly twice.  If
the pointer drifts, the guard tests a different cell each pass and the loop
walks away instead of terminating.

This reports, per layout, the cell the closing ``3`` tests on each pass.
"""


from reexec import instantiate

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine


def probe_cells(template, bits, limit=300):
    """Return the pointer position at each execution of the closing 3."""
    code = instantiate(template, bits)
    close_ip = len(code) - 1
    io = ScriptedIO("")
    m = _Machine(code, io)
    seen = []
    steps = 0
    try:
        while not m.halted and steps < limit:
            if m.ip == close_ip:
                seen.append((m.pos, m.bits.get(m.pos, False)))
            m.step()
            steps += 1
    except EOFError:
        seen.append(("read", None))
    return seen[:6]


def main():
    """Show which cell the closing 3 tests on successive passes."""
    for tpl in ("132{X0}1{X1}3", "132{X0}{X1}3", "132{X0}2{X1}13"):
        print(f"template {tpl!r}")
        for r in range(4):
            bits = [(r >> 1) & 1, r & 1]
            cells = probe_cells(tpl, bits)
            drift = len({c for c, _ in cells if c != "read"})
            print(f"  row {r:02b}: closing-3 tests {cells} "
                  f"distinct cells={drift}")
        print()


if __name__ == "__main__":
    main()
