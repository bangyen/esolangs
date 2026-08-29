r"""Check whether the guard bodies in the zero-result sweeps ever executed.

Four separate ``3``-guard sweeps found nothing.  Before reading that as a
limit of the language, check whether the guards ran at all.

At a ``3`` with ``pos >= 0`` the interpreter either jumps *back* past the
previous ``3`` (TRUE) or *forward* past the next one (FALSE).  Neither falls
into the segment that follows.  So the body between a ``3``-pair is entered
only when the first ``3`` is a NOP -- that is, when ``pos < 0`` -- or by the
second ``3``'s backward jump.

Guards inserted into the walk home sit at ``pos >= 0`` almost everywhere,
so the prediction is that their bodies are dead code.  This instruments the
interpreter to count body executions.
"""

from affine_gen import PRE_ZERO, prologue
from tmpl import instantiate

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine


def body_entries(code, lo, hi, limit=3000):
    """Count steps executed with the cursor inside ``[lo, hi)``."""
    io = ScriptedIO("")
    m = _Machine(code, io)
    hits = 0
    steps = 0
    try:
        while not m.halted and steps < limit:
            if lo <= m.ip < hi:
                hits += 1
            m.step()
            steps += 1
    except EOFError:
        pass
    return hits


def main():
    """Compare guard-body entry for walk-home vs below-zero placement."""
    pre = prologue(PRE_ZERO) + "{X0}{X1}"

    print("--- guard placed in the walk home (pos >= 0) ---")
    for lead in (0, 2, 4, 6):
        tpl = pre + "1" * lead + "3" + "121" + "3" + "1" * (9 - lead) + "21"
        start = len(instantiate(pre, [0, 0])) + lead + 1
        total = 0
        for r in range(4):
            bits = [(r >> 1) & 1, r & 1]
            total += body_entries(instantiate(tpl, bits), start, start + 3)
        print(f"  lead {lead}: body executed {total} times across 4 rows")

    print("\n--- the verified selector, for contrast ---")
    sel = "113{X0}1213"
    for bit in (0, 1):
        code = sel.replace("{X0}", "1" if bit else "2")
        print(f"  {code!r}: body steps {body_entries(code, 3, 7)}")


if __name__ == "__main__":
    main()
