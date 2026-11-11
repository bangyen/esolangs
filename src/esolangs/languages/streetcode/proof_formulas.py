"""Executed command and snapshot-bit bounds."""


# Sharing the floor and kerb removes two vertical road cells per room;
# it adds no commands, tape cells or coordinate bits, so these bounds remain.
# Flat: each marked entry costs a step, the minority polarity (at most T/2),
# so T/2 + 1 ones, marked as the T/2 - 1 zeros, is the worst; the tail's 51
# columns are crossed once.  A tree (the only program with the
# setup ring's ``U``) runs a fixed setup, 294 steps an input, then drives
# only east or south from row 2 past the setup's 4n + 16 columns, short of
# the bottom and east walls, and halts in place.
def _constant_carets(n: int, rows: list[str]) -> int | None:
    """Count carets for a four-row constant layout."""
    if len(rows) == 4 and rows[2].startswith("|C" + "I" * n + "="):
        return rows[2].count("^")
    return None


def execution_terms(n: int, program: str) -> dict[str, int]:
    """Extract the route, constant fill and tree dimensions."""
    rows = program.splitlines()
    carets = _constant_carets(n, rows)
    constant = carets is not None
    tree = not constant and "U" in program
    return {
        "C": int(constant),
        "Q": carets or 0,
        "U": int(tree),
        "H": len(rows) if tree else 0,
        "W": max(map(len, rows)) if tree else 0,
    }


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Identify the constant route and its fill length."""
    carets = _constant_carets(n, program.splitlines())
    return {"C": int(carets is not None), "Q": carets or 0}
