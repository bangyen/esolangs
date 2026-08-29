r"""Distinguish the two ways a re-execution guard fails to terminate.

``whyloop.py`` traced ``132{X0}1{X1}3`` and the paragraph written from it
called every failure "oscillation".  The trace actually shows two different
modes, and the difference matters because only one of them is about the
guard cell:

* **TRUE-side oscillation** (row ``11``): the closing ``3`` tests cell 0 and
  sees True, False, True, ... -- the segment flips the guard cell on every
  pass, so the backjump fires forever;
* **FALSE-side restart** (row ``01``): the closing ``3`` sees False every
  time.  A FALSE test skips *forward* past the next ``3``, and the closing
  ``3`` is the last character, so the skip lands at end-of-program with
  ``pos >= 0`` -- which restarts the whole program with the tape intact.
  Those repeats are restart cycles, not loop passes.

This separates them by checking the cursor after each closing-``3`` test.
"""

from reexec import instantiate

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine


def modes(template, bits, limit=400):
    """Return the sequence of (tested bit, jump direction) at the close."""
    code = instantiate(template, bits)
    close_ip = len(code) - 1
    io = ScriptedIO("")
    m = _Machine(code, io)
    seq = []
    steps = 0
    try:
        while not m.halted and steps < limit:
            if m.ip == close_ip:
                pos, bit = m.pos, m.bits.get(m.pos, False)
                m.step()
                if pos < 0:
                    seq.append("nop")
                elif m.ip < close_ip:
                    seq.append(f"back({int(bit)})")
                else:
                    seq.append(f"fwd->restart({int(bit)})")
            else:
                m.step()
            steps += 1
    except EOFError:
        seq.append("read")
    return seq[:6], m.halted


def main():
    """Show which failure mode each row of the example guard takes."""
    tpl = "132{X0}1{X1}3"
    print(f"template {tpl!r}\n")
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        seq, halted = modes(tpl, bits)
        print(f"  row {r:02b}: {seq} halted={halted}")
    print("\nback(...) is the TRUE-side loop; fwd->restart is the FALSE")
    print("side falling off the end and restarting with the tape intact.")


if __name__ == "__main__":
    main()
