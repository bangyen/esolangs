r"""Target AND, the one monotone table the guard family has not reached.

``monotone.py`` shows the termination route reaches five of the six
monotone tables and none of the ten non-monotone ones, exactly as the
mechanism predicts: a set bit can only add passes, so the "loops" set is
upward-closed and the table is monotone.

AND is monotone, so it should be reachable -- it needs the guard to loop
only when *both* bits are set, i.e. one bit alone must not be enough to add
the extra pass.  That suggests a guard testing a cell both setters touch,
so a single set bit is cancelled and only the pair survives.

This sweeps guard shapes aimed at that, using the fuel prefilter and
confirming any hit with the state-cycle detector.
"""

import itertools

from coverage import confirm, quick_table
from termconv import NAMES


def candidates():
    """Yield guards where both setters can touch a shared cell."""
    entries = ["2" * k for k in range(0, 6)]
    dips = ["1", "11", "111"]
    # place the two setters adjacent, or separated by a wrap-length walk,
    # so their flips can land on the same cell
    gaps = ["", "1", "2", "11", "12", "21", "22", "111", "1111", "121",
            "212", "1212", "2121", "11111", "112", "211"]
    closes = ["", "1", "2", "11", "12", "21", "22", "111"]
    for entry, dip, gap, close in itertools.product(
            entries, dips, gaps, closes):
        yield f"{entry}{dip}3{{X0}}{gap}{{X1}}{close}3"
        yield f"{entry}{dip}3{{X1}}{gap}{{X0}}{close}3"


def main():
    """Search for AND, reporting any new table found on the way."""
    found = {}
    tried = 0
    for tpl in candidates():
        tried += 1
        quick = quick_table(tpl)
        if quick is None or quick in found:
            continue
        exact = confirm(tpl)
        if exact is None or exact in found:
            continue
        found[exact] = tpl
        star = " ***" if exact == "0001" else ""
        print(f"  {exact} {NAMES.get(exact, '?'):14} {tpl!r}{star}",
              flush=True)
    print(f"\ntried {tried}; tables {len(found)}")
    print(f"AND reached: {'0001' in found}")


if __name__ == "__main__":
    main()
