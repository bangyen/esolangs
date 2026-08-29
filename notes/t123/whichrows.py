r"""Tally the halt patterns a single guard family can produce.

The coverage sweep is finding very few tables.  Rather than widen the
family blindly, this asks what the guard shape can express at all.

A row halts exactly when it reaches the closing ``3`` at ``pos < 0``.  The
pointer path is tape-independent, so the only way rows differ is through the
*number of passes* they make, which is decided by the bits under the guard.
That suggests halting is monotone in a specific sense: adding a set bit can
only add passes, never remove them, so the halting rows should form an
up-set or down-set rather than an arbitrary pattern -- which would explain
why OR and the constants appear while XOR does not.

This tabulates the halt patterns actually produced, to see whether they are
so restricted.
"""

from collections import Counter

from coverage import quick_table, templates
from termconv import NAMES


def main():
    """Tally which halt patterns the guard family produces."""
    tally = Counter()
    examples = {}
    for tpl in templates():
        table = quick_table(tpl)
        if table is None:
            tally["reads"] += 1
            continue
        tally[table] += 1
        examples.setdefault(table, tpl)
    total = sum(tally.values())
    print(f"{total} templates, {len(tally) - 1} distinct tables "
          f"(fuel-capped, provisional)\n")
    for table, count in tally.most_common(20):
        if table == "reads":
            print(f"  {count:5}  (rejected: reads stdin)")
            continue
        print(f"  {count:5}  {table} {NAMES.get(table, '?'):14} "
              f"{examples[table]!r}")


if __name__ == "__main__":
    main()
