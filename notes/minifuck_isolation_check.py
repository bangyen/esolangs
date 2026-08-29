"""Check whether a spacer layout leaves both polarities of every parity.

If both p_i and NOT p_i stand as cells, isolation closes: for each i, test
whichever cell is 0 on the target row; n such ==0 tests pin every prefix
parity, which determines the row uniquely.

Sweep separator variants and report, per n, whether every row isolates.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import minifuck_boolean_prototype as gen


def columns(n, sep, base=16, width=16, passes=1):
    """Return each region cell's column after embedding with `sep`."""
    j = gen.Joint(n)
    gen.walk_to(j, base - 1)
    for i in range(n):
        j.emit_setter(i)
        j.emit("[x")
        if i + 1 < n:
            j.emit(sep)
    for _ in range(passes):
        gen.clamp(j)
        gen.walk_to(j, base - 1)
    return {c: j.col(c) for c in range(base, base + width)}


def isolable(cols, n):
    """Count rows that a conjunction of ``== 0`` tests picks out alone."""
    rows = list(range(2**n))
    ok = []
    for row in rows:
        usable = [c for c in cols if cols[c][row] == 0]
        sel = [r for r in rows if all(cols[c][r] == 0 for c in usable)]
        ok.append(sel == [row])
    return sum(ok), len(rows)


SEPS = {
    "[x": "[x",
    "[x[x": "[x[x",
    "[x[x[x": "[x[x[x",
    "[x[x[x[x": "[x[x[x[x",
    "<[x[x": "<[x[x",
    "[x<[x": "[x<[x",
    "[[x": "[[x",
    "[[x[x": "[[x[x",
    "[x[[x": "[x[[x",
}

for n in (2, 3, 4):
    print(f"--- n={n} ---")
    best = None
    for name, sep in SEPS.items():
        for passes in (1, 2, 3):
            cols = columns(n, sep, passes=passes)
            got, total = isolable(cols, n)
            if best is None or got > best[0]:
                best = (got, total, name, passes)
            if got == total:
                print(f"  CLOSES: sep={name!r} passes={passes} -> {got}/{total}")
                break
        else:
            continue
        break
    else:
        print(f"  best: {best[0]}/{best[1]} via sep={best[2]!r} passes={best[3]}")
