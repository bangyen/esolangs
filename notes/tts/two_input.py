r"""Map which two-input tables The Temporary Stack reaches.

``@`` reads a whole *line* and pushes every character's byte code, so both
bits arrive from a single read and a program uses one ``@``, not two.

The drain runs after every word and pops while
``sum(stk[1:]) / 2 > stk[0]``, so with both bytes on the stack the gate is a
threshold over them.  The reach is not purely symmetric -- b0 sits below b1
and cannot be duplicated alone, which makes the two bits enter with
different weights and puts asymmetric tables like ``(0, 1, 0, 0)`` in range
-- but it is monotone, which is what leaves the negated tables out.

Entries are read under the emission-vs-silence convention (1 = printed
something), the same convention walls.md accepts for ArrowQueue and Point
Break.
"""

import itertools

from probe import go

BITS = ("0", "1")


def table(source):
    """Return the 4-entry emission table for a two-input program, or None.

    Under the emission convention an entry is 1 when the program prints and
    0 when it stays silent, so the answer does not have to be a digit.
    """
    out = []
    for b0 in BITS:
        for b1 in BITS:
            text, status = go(source, b0 + b1, limit=800)
            if status != "halt":
                return None
            out.append(1 if text else 0)
    return tuple(out)


NAMES = {
    (0, 0, 0, 1): "AND", (0, 1, 1, 1): "OR", (0, 1, 1, 0): "XOR",
    (1, 1, 1, 0): "NAND", (1, 0, 0, 0): "NOR", (1, 0, 0, 1): "XNOR",
    (0, 0, 1, 1): "b0", (0, 1, 0, 1): "b1",
    (1, 1, 0, 0): "NOT b0", (1, 0, 1, 0): "NOT b1",
    (0, 0, 0, 0): "const0", (1, 1, 1, 1): "const1",
    (0, 1, 0, 0): "b1 AND NOT b0", (0, 0, 1, 0): "b0 AND NOT b1",
    (1, 0, 1, 1): "NOT b1 OR b0", (1, 1, 0, 1): "NOT b0 OR b1",
}


def main():
    """Sweep short one-read programs for the tables they reach."""
    words = ["@", "+", "o", "O", "v1", "v48", "v49", "v50", "v51", "v97",
             "v98", "v99", "v100", "v999"]
    found = {}
    for length in range(2, 5):
        for combo in itertools.product(words, repeat=length):
            if combo.count("@") != 1:
                continue
            src = " ".join(combo)
            tbl = table(src)
            if tbl is not None and tbl not in found:
                found[tbl] = src
        print(f"through length {length}: {len(found)} tables", flush=True)
    print()
    for tbl in sorted(found):
        print(f"  {tbl} {NAMES.get(tbl, '?'):8} <- {found[tbl]!r}")


if __name__ == "__main__":
    main()
