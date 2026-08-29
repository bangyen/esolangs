r"""Check whether complementing a reachable table closes the coverage gap.

The union of the two routes is 9/16.  The seven missing are AND, NAND,
NOR, both ``AND NOT`` tables and both ``OR NOT`` tables.

Complementation is worth checking because the printing route's answer digit
is chosen by the prologue constant: 0xCF prints ``'0'`` and 0xCE prints
``'1'``, and swapping them inverts every row at once.  That is exactly why
the affine set is closed under complement (XOR and XNOR both appear, b0 and
NOT b0 both appear).

If the same trick applied to the termination route it would give NOR from
OR immediately.  But the convention fixes halt = 0 and loop = 1, so
inverting the answer means swapping which rows halt -- not something a
prologue constant can do.  This checks whether the complement of each
missing table is reachable, which says whether an inversion device would
close the gap.
"""

from termconv import NAMES

AFFINE = {"0000", "1111", "0011", "1100", "0101", "1010", "0110", "1001"}
TERMINATION = {"0000", "1111", "0111", "0101", "0011"}


def complement(table):
    """Return the table with every entry flipped."""
    return "".join("1" if c == "0" else "0" for c in table)


def main():
    """For each missing table, report whether its complement is reachable."""
    reached = AFFINE | TERMINATION
    missing = [t for t in sorted(NAMES) if t not in reached]
    print(f"missing: {len(missing)}\n")
    for table in missing:
        comp = complement(table)
        where = []
        if comp in AFFINE:
            where.append("affine/print")
        if comp in TERMINATION:
            where.append("monotone/halt")
        status = ", ".join(where) if where else "also missing"
        print(f"  {table} {NAMES[table]:14} complement {comp} "
              f"{NAMES[comp]:14} -> {status}")
    print("\nAn inversion device on the printing route flips the answer")
    print("digit, so it maps affine tables to affine tables and adds")
    print("nothing.  Closing the gap needs a table whose complement is")
    print("reachable on the *other* route, and an inverter there.")


if __name__ == "__main__":
    main()
