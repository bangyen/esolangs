r"""The non-affine operator is conditional *re-execution*, not flipping.

Every sweep so far rearranged flips, and a flip is XOR: any composition of
them is affine in the inputs, which is why only the eight affine tables ever
appeared.  The one operator in 123 that is not a flip is a TRUE-backward
``3``, which re-runs its segment.  If that segment contains an instantiated
setter, the setter's flip executes a number of times that depends on the
guard cell -- and a count is not linear.

Concretely, with b0 recorded in the guard cell and ``{X1}`` inside the
segment:

* b0 = 0: the guard is FALSE, the segment runs once, so cell ``c`` ends
  holding b1;
* b0 = 1: the guard is TRUE, the segment runs twice, so ``c`` holds
  b1 XOR b1 = 0.

That is ``c = b1 AND NOT b0`` -- a genuine minterm, from which the affine
endgame already built (prologue + walk home) reaches the AND/OR class.

The design constraints, all established by earlier scripts here:

* the opening ``3`` must be entered as a NOP, i.e. at ``pos < 0``, since at
  ``pos >= 0`` a FALSE test skips the whole segment (``guardentry.py``);
* the segment must flip the guard cell, so the second pass exits rather
  than looping forever;
* the exit path needs a defined landing, or the program restarts.

This module builds one candidate and traces it, checking the pass counts
before looking at any table.
"""

from tmpl import ONE, ZERO

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine


def instantiate(template, bits):
    """Substitute both placeholders with the neutral setter pair."""
    out = template.replace("{X0}", ONE if bits[0] else ZERO)
    return out.replace("{X1}", ONE if bits[1] else ZERO)


def trace(template, bits, limit=400):
    """Run one row, returning the per-3 events and the final tape."""
    code = instantiate(template, bits)
    io = ScriptedIO("")
    m = _Machine(code, io)
    events = []
    steps = 0
    try:
        while not m.halted and steps < limit:
            if m.ip < len(code) and code[m.ip] == "3":
                before = m.ip
                pos = m.pos
                m.step()
                if pos < 0:
                    events.append(("nop", pos))
                elif m.ip < before:
                    events.append(("back", pos))
                else:
                    events.append(("fwd", pos))
            else:
                m.step()
            steps += 1
    except EOFError:
        events.append(("read", m.pos))
    tape = tuple(sorted(k for k, v in m.bits.items() if v))
    return code, events, tape, io.getvalue(), m.halted


def main():
    """Trace a hand-built re-execution guard on all four rows."""
    # Walk below zero so the opening 3 is a NOP, record b0 under the guard,
    # put {X1} inside the guarded segment so its flip count depends on b0.
    tpl = "111{X0}3{X1}13"
    print(f"template {tpl!r}\n")
    for r in range(4):
        bits = [(r >> 1) & 1, r & 1]
        code, events, tape, out, halted = trace(tpl, bits)
        backs = sum(1 for kind, _ in events if kind == "back")
        print(f"  row {r:02b} {code!r}")
        print(f"     3-events {events[:6]} backjumps={backs}")
        print(f"     tape {tape} out={out!r} halted={halted}")


if __name__ == "__main__":
    main()
