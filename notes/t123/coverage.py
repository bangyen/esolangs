r"""Measure how many two-input tables the termination convention reaches.

The first attempt at this ran ``run_until_halt_or_cycle`` on every
candidate and never finished: proving non-termination costs far more than
observing it, and most rows loop.

This is two-stage.  A cheap fuel-capped run classifies each row as
halt-or-not, which is exact for the halting rows and merely *provisional*
for the rest; only when a template's provisional table is one not yet
found does the state-cycle detector run, confirming that every row called
"loops" really does.  The detector is the same one the repo uses for Point
Break, so a confirmed row is proved non-terminating rather than assumed.
"""

import itertools

from reexec import instantiate
from termconv import NAMES

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine
from esolangs.vm import run_until_halt_or_cycle

FUEL = 3000


def quick_table(template):
    """Provisional table by fuel cap; None if any row reads stdin."""
    bits_out = []
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        code = instantiate(template, bits)
        machine = _Machine(code, ScriptedIO(""))
        steps = 0
        try:
            while not machine.halted and steps < FUEL:
                machine.step()
                steps += 1
        except EOFError:
            return None
        bits_out.append("0" if machine.halted else "1")
    return "".join(bits_out)


def confirm(template):
    """Re-decide with the state-cycle detector; None if a row reads."""
    bits_out = []
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        machine = _Machine(instantiate(template, bits), ScriptedIO(""))
        try:
            halted = run_until_halt_or_cycle(machine)
        except EOFError:
            return None
        bits_out.append("0" if halted else "1")
    return "".join(bits_out)


def templates():
    """Yield the guard family to measure."""
    entries = ["2" * k for k in range(0, 7)]
    dips = ["1", "11", "111"]
    bodies = ["", "1", "11", "111", "1111", "11111", "12", "121", "1211",
              "112", "1121", "1212", "2112", "2121", "21", "211", "2211"]
    for entry, dip, body in itertools.product(entries, dips, bodies):
        yield f"{entry}{dip}3{{X0}}{body}{{X1}}3"
        yield f"{entry}{dip}3{{X1}}{body}{{X0}}3"
        yield f"{entry}{dip}3{{X0}}{body}{{X1}}13"
        yield f"{entry}{dip}3{{X0}}{body}{{X1}}23"


def main():
    """Prefilter by fuel, confirm new tables with the detector."""
    found = {}
    lines = []

    def log(text):
        """Print and persist so progress survives a kill."""
        print(text, flush=True)
        lines.append(text)
        with open("coverage_results.txt", "w") as handle:
            handle.write("\n".join(lines) + "\n")

    tried = 0
    confirmed = 0
    for tpl in templates():
        tried += 1
        quick = quick_table(tpl)
        if quick is None or quick in found:
            continue
        exact = confirm(tpl)
        confirmed += 1
        if exact is None or exact in found:
            continue
        found[exact] = tpl
        log(f"  {exact} {NAMES.get(exact, '?'):14} {tpl!r}")
    log(f"\ntried {tried} templates, ran the detector on {confirmed}")
    log(f"tables reached: {len(found)}/16")
    missing = [NAMES[k] for k in sorted(NAMES) if k not in found]
    log(f"missing ({len(missing)}): {', '.join(missing)}")


if __name__ == "__main__":
    main()
