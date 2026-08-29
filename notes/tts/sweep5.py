r"""Sweep to five words with one bit per input line.

``b0test.py`` shows the earlier length-4 multiline cap hid the b0 witness
``v97 @ + + @``.  Five words is where duplicating b0 before the second read
becomes expressible, so the reach has to be measured there rather than
inferred from four.

``:`` and ``€`` stay out of the vocabulary: ``:`` loops inside a single
``step()`` and hangs on an empty stack, and ``€`` picks a command with
``secrets.choice``, so it is nondeterministic and must never be emitted.
"""

import itertools
import sys

from invert import table
from two_input import NAMES

NL = chr(10)


def main():
    """Sweep two-read programs to the given length, one bit per line."""
    max_len = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    consts = [f"v{n}" for n in
              (0, 1, 2, 47, 48, 49, 50, 51, 96, 97, 98, 99, 100, 145, 146,
               147, 195, 196)]
    words = ["@", "+", "o", "O", *consts]
    found = {}
    for length in range(2, max_len + 1):
        for combo in itertools.product(words, repeat=length):
            if combo.count("@") != 2:
                continue
            src = " ".join(combo)
            tbl = table(src, sep=NL)
            if tbl is not None and tbl not in found:
                found[tbl] = src
        print(f"through length {length}: {len(found)}/16", flush=True)
    print()
    for tbl in sorted(NAMES):
        mark = f"<- {found[tbl]!r}" if tbl in found else "-- NOT REACHED"
        print(f"  {tbl} {NAMES[tbl]:14} {mark}")
    missing = [NAMES[t] for t in sorted(NAMES) if t not in found]
    print(f"\nmissing ({len(missing)}): {', '.join(missing)}")


if __name__ == "__main__":
    main()
