r"""Two-channel design: one input in the pointer, one in the tape.

``guardentry.py`` shows why every guard sweep found nothing -- the bodies
were dead code.  A ``3`` at ``pos >= 0`` jumps away rather than falling
through, so a segment is entered only when its opening ``3`` is a NOP, which
needs ``pos < 0``.

There is a second reason to redesign rather than re-place.  If a guard's
TRUE and FALSE paths reconverge at the same cursor *and* the same pointer,
the guard contributes ``t * (difference in flips)`` for the tested cell
``t``.  ``t`` is affine in the inputs, so the tape stays affine and no
arrangement of such guards can build AND.  The paths must therefore exit at
**different pointer positions**, so that later code reads a cell chosen by
the first bit -- the pointer carrying the indicator that tape XOR cannot.

The setters are per-input free, so this mixes them:

* ``{X0}`` uses the one-character setter ``1``/``2``, whose members displace
  the pointer oppositely -- position now encodes b0;
* ``{X1}`` uses the neutral pair ``12``/``21`` -- tape encodes b1.

A guard entered below zero then tests a cell whose index depends on b0,
while its content depends on b1.
"""

import itertools

from tmpl import ONE, ZERO, run

AFFINE = {("0", "1", "1", "0"), ("1", "0", "0", "1"),
          ("0", "0", "1", "1"), ("1", "1", "0", "0"),
          ("0", "1", "0", "1"), ("1", "0", "1", "0"),
          ("0", "0", "0", "0"), ("1", "1", "1", "1")}

NAMES = {
    ("0", "0", "0", "1"): "AND", ("0", "1", "1", "1"): "OR",
    ("1", "1", "1", "0"): "NAND", ("1", "0", "0", "0"): "NOR",
    ("0", "1", "0", "0"): "b1 AND NOT b0",
    ("0", "0", "1", "0"): "b0 AND NOT b1",
    ("1", "0", "1", "1"): "NOT b1 OR b0",
    ("1", "1", "0", "1"): "NOT b0 OR b1",
}


def instantiate_mixed(template, bits):
    """``{X0}`` takes the +-1 setter, ``{X1}`` the neutral pair."""
    out = template.replace("{X0}", "1" if bits[0] else "2")
    return out.replace("{X1}", ONE if bits[1] else ZERO)


def table_of_mixed(template, limit=4000):
    """Return the four printed digits, or None if a row misbehaves."""
    rows = []
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        out, status = run(instantiate_mixed(template, bits), limit)
        if status != "halt" or len(out) != 1 or out not in "01":
            return None
        rows.append(out)
    return tuple(rows)


def lengths_ok(template):
    """Whether every instantiation has the same length."""
    return len({len(instantiate_mixed(template, [(r >> 1) & 1, r & 1]))
                for r in range(4)}) == 1


def main():
    """Sweep two-channel templates with a below-zero guard entry."""
    found = {}
    tried = 0
    prefixes = ["1" * k for k in range(1, 5)]
    bodies = ["", "1", "2", "12", "21", "121", "212", "112", "221"]
    tails = ["1" * k + "2" + "1" for k in range(0, 13)]
    for pre, gap, body, tail in itertools.product(
            prefixes, ["", "1", "2", "12", "21"], bodies, tails):
        tpl = f"{pre}3{{X0}}{body}3{gap}{{X1}}{tail}"
        if not lengths_ok(tpl):
            continue
        tried += 1
        tbl = table_of_mixed(tpl)
        if tbl is None or tbl in AFFINE:
            continue
        if tbl not in found:
            found[tbl] = tpl
    print(f"tried {tried} two-channel templates")
    print(f"non-affine tables: {len(found)}\n")
    for tbl, tpl in sorted(found.items()):
        print(f"  {''.join(tbl)} {NAMES.get(tbl, '?'):14} {tpl!r}")


if __name__ == "__main__":
    main()
