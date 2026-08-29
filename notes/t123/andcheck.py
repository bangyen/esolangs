r"""Ask directly whether AND is reachable, rather than sweeping for it.

AND is the one monotone table the guard family has not produced, and
``monotone.py`` predicts monotone tables are the reachable ones -- so its
absence is either a gap in the shapes tried or a second constraint the
monotonicity argument does not capture.

AND loops on row ``11`` alone, so it needs the guard to gain its extra pass
only when *both* bits are set.  Each setter contributes independently to
the tape, and the guard tests one cell, so the question is whether one cell
can end up set exactly on row ``11``.  With ``12``/``21`` the two setters
flip different cells (current versus next), so a cell is touched by at most
one setter unless the walk between them lines the two up.

This checks that directly: for each cell, which rows leave it set?  A cell
set exactly on row ``11`` is an AND indicator; if no arrangement produces
one, AND needs a different mechanism rather than a longer search.
"""


from gen import _Joint


def cell_patterns(gap):
    """Return, per cell, the rows that leave it set for a given gap."""
    j = _Joint(2)
    j.emit("22222")
    j.emit_pair(0)
    if gap:
        j.emit(gap)
    j.emit_pair(1)
    cells = {}
    for cell in range(-3, 14):
        pattern = tuple(int(m.bits.get(cell, False)) for m in j.ms)
        if any(pattern):
            cells[cell] = pattern
    return j.template(), cells


def main():
    """Look for a cell set exactly on row 11 (an AND indicator)."""
    gaps = ["", "1", "2", "11", "12", "21", "22", "121", "212", "111",
            "222", "1212", "2121", "1122", "2211"]
    found = []
    for gap in gaps:
        tpl, cells = cell_patterns(gap)
        for cell, pattern in cells.items():
            if pattern == (0, 0, 0, 1):
                found.append((tpl, cell, pattern))
    print("cell patterns per gap (rows 00, 01, 10, 11):\n")
    for gap in gaps[:6]:
        tpl, cells = cell_patterns(gap)
        shown = dict(sorted(cells.items()))
        print(f"  gap {gap!r:6} {shown}")
    print(f"\ncells set exactly on row 11 (AND indicators): {len(found)}")
    for tpl, cell, pattern in found[:5]:
        print(f"  {tpl!r} cell {cell} pattern {pattern}")


if __name__ == "__main__":
    main()
