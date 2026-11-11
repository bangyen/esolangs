"""Executed command and snapshot-bit bounds."""


# Sharing the floor and kerb removes two vertical road cells per room;
# it adds no commands, tape cells or coordinate bits, so these bounds remain.
# Flat: each marked entry costs a step, the minority polarity (at most T/2),
# so T/2 + 1 ones, marked as the T/2 - 1 zeros, is the worst; the tail's 51
# columns are crossed once.  A tree (the only program with the
# setup ring's ``U``) runs a fixed setup, 294 steps an input, then drives
# only east or south from row 2 past the setup's 4n + 16 columns, short of
# the bottom and east walls, and halts in place.
def execution_terms(n: int, program: str) -> dict[str, int]:
    """Extract the route, constant fill and tree dimensions."""
    rows = program.splitlines()
    constant = len(rows) == 4 and rows[2].startswith("|C" + "I" * n + "=")
    tree = not constant and "U" in program
    return {
        "C": int(constant),
        "Q": rows[2].count("^") if constant else 0,
        "U": int(tree),
        "H": len(rows) if tree else 0,
        "W": max(map(len, rows)) if tree else 0,
    }


def workspace(n: int, program: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    rows = program.splitlines()
    if len(rows) == 4 and rows[2].startswith("|C" + "I" * n + "="):
        # Fixed row, heading and latch, CP, two six-bit cells and halt: 27 bits.
        bit = rows[2].count("^") - 48
        return 27 + bl(n + 52 + bit) + 2 * bl(n)
    # Peak car state is 13 + bl(width), width = 2T + 57 + G.  A tree holds
    # 2n + 4 cells under 100 and a narrower car, inside nT from n = 5.
    return (
        n * (1 << n)
        + 2 * n
        + 25
        + bl(
            (1 << (n + 1)) + 57 + sum(max(51, (1 << (k - 1)) + 3) for k in range(1, n))
        )
        + 2 * bl(n)
    )
