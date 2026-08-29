r"""Verify the short OR witness found by the coverage sweep.

The first OR witness was ``2113{X0}1111{X1}3`` (17 characters).  The
coverage sweep reaches the same table with ``13{X0}{X1}3`` -- eight
characters, and short enough to trace by hand -- so this checks it on its
own and prints the per-row behaviour that produces the table.
"""

from reexec import instantiate

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine
from esolangs.vm import run_until_halt_or_cycle

TEMPLATE = "13{X0}{X1}3"


def main():
    """Show each row's instantiation, halt verdict, and the table."""
    bits_out = []
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        code = instantiate(TEMPLATE, bits)
        machine = _Machine(code, ScriptedIO(""))
        halted = run_until_halt_or_cycle(machine)
        bits_out.append("0" if halted else "1")
        print(f"  row {r:02b} b0={bits[0]} b1={bits[1]}  {code!r:14} "
              f"{'halts' if halted else 'loops'} -> {bits_out[-1]}")
    table = "".join(bits_out)
    print(f"\n  table {table} "
          f"({'OR' if table == '0111' else 'unexpected'})")
    lengths = {len(instantiate(TEMPLATE, [(r >> 1) & 1, r & 1]))
               for r in range(4)}
    print(f"  all instantiations same length: {len(lengths) == 1} {lengths}")


if __name__ == "__main__":
    main()
