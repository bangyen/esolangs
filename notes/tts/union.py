r"""The verified union of reachable two-input tables, each witness re-run.

Separate sweeps used different vocabularies, lengths and input conventions,
so this collects every witness and re-executes it under the convention it
was found with -- the reported count is one verified set rather than a
maximum over runs.

The per-line convention (one bit per ``input()`` call) is the one the
language's own tests used, and it reaches strictly more: ``@ + @``
duplicates b0 while it is still the top of the stack, which a single-line
read cannot do.
"""

from invert import table
from two_input import NAMES

NL = chr(10)

# (source, separator) -- "" feeds both bits on one line, "\n" one per line.
WITNESSES = [
    ("@ @", NL),
    ("v49 @ @ v1", NL),
    ("v48 @ @", NL),
    ("v96 @ + @ v47", NL),
    ("v96 @ @ + v47", NL),
    ("@ @ v49", NL),
    ("@ @ +", NL),
    ("@ @ v50", NL),
    ("@ @ v51", NL),
    # single-line witnesses, kept to show the convention is not the whole story
    ("v49 @ v1", ""),
    ("v48 @", ""),
    ("@ v49", ""),
    ("@ +", ""),
    ("@ v50", ""),
    ("@ v51", ""),
    ("v97 @ + +", ""),
]


def main():
    """Re-execute every witness and report the verified union."""
    found = {}
    for src, sep in WITNESSES:
        tbl = table(src, sep=sep)
        if tbl is None:
            print(f"  (dropped, not clean on all rows) {src!r}")
            continue
        found.setdefault(tbl, (src, "per-line" if sep else "one-line"))
    print(f"\nverified union: {len(found)}/16 tables\n")
    for tbl in sorted(NAMES):
        if tbl in found:
            src, conv = found[tbl]
            mark = f"<- {src!r} ({conv})"
        else:
            mark = "-- NOT REACHED"
        print(f"  {tbl} {NAMES[tbl]:14} {mark}")
    missing = [NAMES[t] for t in sorted(NAMES) if t not in found]
    print(f"\nmissing ({len(missing)}): {', '.join(missing)}")


if __name__ == "__main__":
    main()
