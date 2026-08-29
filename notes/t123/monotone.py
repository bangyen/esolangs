r"""Test whether the termination route is bounded to monotone tables.

``whichrows.py`` finds the guard family reaches exactly five tables --
const0, const1, OR, b0, b1 -- and those are precisely the monotone ones
among the sixteen (a table is monotone when setting an input bit from 0 to
1 never turns a 1 answer into a 0).

The mechanism predicts that.  A row halts iff it reaches the closing ``3``
at ``pos < 0``, and which passes it makes is decided by the bits under the
guard: a set bit can only cause an additional pass, never remove one.  So
the "loops" set is upward-closed in the inputs, and the computed table is
monotone.

If the prediction holds, the missing tables are not a coverage gap in the
sweep but a property of the construction: AND is monotone and *should* be
reachable by a wider family, while XOR, NAND, NOR and every negated table
should not be reachable by this route at all.

This checks the found tables against monotonicity, and reports which
monotone tables remain unreached -- the honest target list.
"""

from termconv import NAMES

FOUND = ["0000", "1111", "0111", "0101", "0011"]


def monotone(table):
    """Whether flipping an input 0 -> 1 never turns a 1 answer into 0."""
    value = {(r >> 1, r & 1): int(table[r]) for r in range(4)}
    for b0, b1 in value:
        for nb0, nb1 in ((1, b1), (b0, 1)):
            if ((nb0, nb1) in value and (nb0, nb1) != (b0, b1)
                    and value[(b0, b1)] > value[(nb0, nb1)]):
                return False
    return True


def main():
    """Classify all sixteen tables and compare with what was reached."""
    mono = [t for t in sorted(NAMES) if monotone(t)]
    print(f"monotone tables ({len(mono)}): "
          f"{', '.join(NAMES[t] for t in mono)}\n")
    print("reached by the guard family:")
    for t in sorted(FOUND):
        print(f"  {t} {NAMES[t]:14} monotone={monotone(t)}")
    gap = [t for t in mono if t not in FOUND]
    print(f"\nmonotone but not yet reached ({len(gap)}): "
          f"{', '.join(NAMES[t] for t in gap)}")
    nonmono = [t for t in sorted(NAMES) if not monotone(t)]
    print(f"non-monotone, predicted unreachable by this route "
          f"({len(nonmono)}): {', '.join(NAMES[t] for t in nonmono)}")


if __name__ == "__main__":
    main()
