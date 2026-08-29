r"""Verify the halt-vs-loop tables against the repo's own hang detector.

``splitguard.py`` finds ``2113{X0}1111{X1}3`` halting only on row ``00``,
which under the termination convention (halt = 0, loop = 1, see
``run_point_break`` in ``tests/tools/boolean_runners.py``) is **NOR** -- the
first non-affine table reached here.

The convention does not look at output, so the garbage the looping rows
print before diverging is irrelevant to the answer.  What does matter is
that "loops" is decided properly rather than by a fuel cap, so this uses
``esolangs.vm.run_until_halt_or_cycle``, the same state-cycle detector the
repo uses for Point Break: a deterministic machine that revisits an exact
internal state is proved non-terminating.
"""

from reexec import instantiate

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine
from esolangs.vm import run_until_halt_or_cycle

NAMES = {
    "0001": "AND", "0111": "OR", "0110": "XOR", "1110": "NAND",
    "1000": "NOR", "1001": "XNOR", "0011": "b0", "0101": "b1",
    "1100": "NOT b0", "1010": "NOT b1", "0000": "const0", "1111": "const1",
    "0100": "b1 AND NOT b0", "0010": "b0 AND NOT b1",
    "1011": "NOT b1 OR b0", "1101": "NOT b0 OR b1",
}


def table_by_termination(template):
    """Return the truth table under halt = 0, loop = 1."""
    bits_out = []
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        code = instantiate(template, bits)
        machine = _Machine(code, ScriptedIO(""))
        try:
            halted = run_until_halt_or_cycle(machine)
        except EOFError:
            return None
        bits_out.append("0" if halted else "1")
    return "".join(bits_out)


def main():
    """Check the candidate and a few relatives against the detector."""
    for tpl in ("2113{X0}1111{X1}3",
                "2113{X0}121{X1}3",
                "2113{X1}1111{X0}3"):
        table = table_by_termination(tpl)
        if table is None:
            print(f"  {tpl!r:26} -> reads stdin (rejected)")
            continue
        print(f"  {tpl!r:26} -> {table} {NAMES.get(table, '?')}")


if __name__ == "__main__":
    main()
