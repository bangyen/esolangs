r"""Sweep which two-input tables the termination convention reaches.

``termconv.py`` verifies ``2113{X0}1111{X1}3`` computes **OR** under
halt = 0 / loop = 1, decided by ``esolangs.vm.run_until_halt_or_cycle``
rather than a fuel cap.  OR is not affine, so this route escapes the
ceiling that bounds the printing construction at eight tables.

This sweeps the guard family under that convention and reports which of the
sixteen tables come out.  The convention is the one walls.md already
accepts for ArrowQueue and Point Break, so a table reached here counts on
the same terms.
"""

import itertools

from termconv import NAMES, table_by_termination


def main():
    """Sweep guard layouts and collect the tables they compute."""
    entries = ["2" * k for k in range(0, 7)]
    dips = ["1", "11", "111"]
    bodies = ["", "1", "11", "111", "1111", "11111", "12", "121", "1211",
              "112", "1121", "1212", "2112", "2121", "21", "211"]
    found = {}
    tried = 0
    for entry, dip, body in itertools.product(entries, dips, bodies):
        for tpl in (f"{entry}{dip}3{{X0}}{body}{{X1}}3",
                    f"{entry}{dip}3{{X1}}{body}{{X0}}3",
                    f"{entry}{dip}3{{X0}}{body}{{X1}}13",
                    f"{entry}{dip}3{{X0}}{body}{{X1}}23"):
            tried += 1
            table = table_by_termination(tpl)
            if table is None:
                continue
            if table not in found:
                found[table] = tpl
    print(f"tried {tried} layouts")
    print(f"tables reached: {len(found)}/16\n")
    for key in sorted(NAMES):
        mark = f"<- {found[key]!r}" if key in found else "-- not reached"
        print(f"  {key} {NAMES[key]:14} {mark}")


if __name__ == "__main__":
    main()
