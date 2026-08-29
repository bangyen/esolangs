r"""Check the two-channel guards are live and the rows exit at different spots.

``twochannel.py`` returns zero, but a zero is only informative if the guard
actually ran.  ``guardentry.py`` established the trap: a guard body at
``pos >= 0`` is dead code, and four earlier sweeps searched over it.

This checks the two things the design needs:

* the guard body executes (the ``3`` is entered as a NOP from below zero);
* the TRUE and FALSE paths leave the guard at *different pointer
  positions*, which is what lets a later read depend on the first bit.  If
  they reconverge, the guard's whole contribution is affine and no table
  beyond the eight already built can appear.
"""

from twochannel import instantiate_mixed

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine


def guard_report(template, limit=3000):
    """Return per-row (body steps, pointer at each 3, final pointer)."""
    rows = []
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        code = instantiate_mixed(template, bits)
        io = ScriptedIO("")
        m = _Machine(code, io)
        at_three = []
        steps = 0
        try:
            while not m.halted and steps < limit:
                if m.ip < len(code) and code[m.ip] == "3":
                    at_three.append(m.pos)
                m.step()
                steps += 1
        except EOFError:
            at_three.append("READ")
        rows.append((code, at_three[:6], m.pos))
    return rows


def main():
    """Report guard liveness for a few two-channel shapes."""
    for tpl in ("113{X0}12132{X1}1111111121",
                "1113{X0}213{X1}111111111121",
                "113{X0}3{X1}11111111121"):
        print(f"template {tpl!r}")
        for code, threes, endpos in guard_report(tpl):
            print(f"   {code!r:34} 3s at pos {threes} end {endpos}")
        print()


if __name__ == "__main__":
    main()
