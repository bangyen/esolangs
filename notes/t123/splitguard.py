r"""Build on the guards whose rows split on halting.

``entrytest.py`` refutes the tempting impossibility argument: rows *can*
reach the closing ``3`` at different positions even though every position
map is tape-independent, because a row that takes an extra pass has made a
different number of moves by the time it gets there.

``2113{X0}121{X1}3`` halts on rows ``00`` and ``10`` and loops on ``01``
and ``11`` -- split on b1.  Under the termination convention that is
already a one-input function; what is needed for a table is for the halting
rows to *print* and the others to be brought back to a halt too, or for the
split itself to be widened to depend on both bits.

This explores both: first whether the split can be made to depend on b0 and
b1 jointly, then whether the halting rows can carry a printed digit.
"""

import itertools

from reexec import instantiate

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine


def halt_pattern(template, limit=600):
    """Return the per-row halt pattern and outputs, or None on a read."""
    rows = []
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        code = instantiate(template, bits)
        io = ScriptedIO("")
        m = _Machine(code, io)
        steps = 0
        try:
            while not m.halted and steps < limit:
                m.step()
                steps += 1
        except EOFError:
            return None
        rows.append((m.halted, io.getvalue()))
    return rows


NONAFFINE_HALTS = {
    (True, True, True, False), (False, False, False, True),
    (True, False, False, False), (False, True, True, True),
    (True, True, False, True), (False, False, True, False),
    (True, False, True, True), (False, True, False, False),
}


def main():
    """Sweep for halt patterns that depend on both bits."""
    entries = ["2" * k for k in range(1, 6)]
    dips = ["1", "11", "111"]
    bodies = ["1", "11", "111", "1111", "12", "121", "1211", "112",
              "1121", "1212", "2112"]
    found = {}
    tried = 0
    for entry, dip, body in itertools.product(entries, dips, bodies):
        for tpl in (f"{entry}{dip}3{{X0}}{body}{{X1}}3",
                    f"{entry}{dip}3{{X1}}{body}{{X0}}3"):
            tried += 1
            rows = halt_pattern(tpl)
            if rows is None:
                continue
            pattern = tuple(h for h, _ in rows)
            if pattern in NONAFFINE_HALTS and pattern not in found:
                found[pattern] = (tpl, [o for _, o in rows])
    print(f"tried {tried} guards")
    print(f"{len(found)} non-affine halt patterns\n")
    for pattern, (tpl, outs) in sorted(found.items()):
        marks = "".join("H" if h else "." for h in pattern)
        print(f"  {marks}  {tpl!r:30} out={outs}")


if __name__ == "__main__":
    main()
