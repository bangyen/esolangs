r"""Explain how the guard computes OR when every cell is affine.

``andcheck.py`` shows every cell ends as a fixed XOR of the bits that
touched it -- ``(0,1,1,0)``, ``(0,1,0,1)``, ``(1,0,0,1)`` and so on -- and
``(0,0,0,1)`` never appears.  Flips cannot make a product.

Yet ``13{X0}{X1}3`` computes OR, whose table ``0111`` is not affine.  The
resolution must be that the halt verdict is not a single cell test: the
guard is executed repeatedly, and what it tests is the *pointer position*:
a closing ``3`` reached below zero is a NOP and the row falls through, so
the verdict accumulates over passes rather than reading one affine cell.

This traces the short OR witness pass by pass, showing which cell each test
reads and what it finds, to confirm that reading.
"""

from reexec import instantiate

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine

TEMPLATE = "13{X0}{X1}3"


def main():
    """Show the cell and value each guard test reads, per row."""
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        code = instantiate(TEMPLATE, bits)
        io = ScriptedIO("")
        m = _Machine(code, io)
        tests = []
        steps = 0
        while not m.halted and steps < 60:
            if m.ip < len(code) and code[m.ip] == "3":
                tests.append((m.ip, m.pos, int(m.bits.get(m.pos, False))))
            m.step()
            steps += 1
        verdict = "halts" if m.halted else "loops"
        print(f"  row {r:02b} {code!r}: {verdict}")
        print(f"      (ip, pos, bit) tests: {tests[:8]}")


if __name__ == "__main__":
    main()
