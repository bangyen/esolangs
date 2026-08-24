"""Prototype: compact an ABCDirection grid by deleting dead rows/cols.

Deleting an all-B row or column is behaviour-preserving: B is a no-op, every
turn happens at a live cell, and a uniform deletion shifts all live cells
together so their relative geometry (and the row-0 / bottom-row wraps) is
unchanged.  The one hazard is horizontal: ``_parse`` stops at the first
``DDDDDD``, so removing a B column that separated D cells can fuse them into
a false terminator.  Rows carry no such hazard.
"""


def compact(rows: list[str]) -> list[str]:
    """Delete every all-B row, and every all-B column that is safe to delete."""
    height = len(rows)
    width = len(rows[0])

    keep_rows = [y for y in range(height) if set(rows[y]) != {"B"}]
    rows = [rows[y] for y in keep_rows]

    cols = list(zip(*rows))
    dead = [x for x in range(width) if set(cols[x]) == {"B"}]

    keep_cols = list(range(width))
    for x in dead:
        trial = [c for c in keep_cols if c != x]
        # The real terminator is the trailing DDDDDD on the last row; a run
        # anywhere else (or earlier on that row) would truncate the program.
        ok = True
        for index, row in enumerate(rows):
            line = "".join(row[c] for c in trial)
            body = line[:-6] if index == len(rows) - 1 else line
            if "DDDDDD" in body:
                ok = False
                break
        if ok:
            keep_cols = trial

    return ["".join(row[c] for c in keep_cols) for row in rows]
