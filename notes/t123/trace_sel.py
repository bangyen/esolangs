"""Trace the length-7 selector to attribute its mechanism correctly.

The point of this file is that ``docs/walls.md``'s failure history is
mechanisms asserted without tracing, so the witness's *behaviour* (verified
in ``verify_sel.py``) and its *mechanism* are established separately.
"""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine

TEMPLATE = "113{X0}1213"
SETTER = {0: "1", 1: "2"}


def trace(code, limit=60):
    """Print each step: cursor, command, pointer, byte, and any jump taken."""
    io = ScriptedIO("")
    machine = _Machine(code, io)
    steps = 0
    while not machine.halted and steps < limit:
        ip, pos = machine.ip, machine.pos
        char = machine.code[ip] if ip < machine.n else "END"
        before = io.getvalue()
        machine.step()
        note = ""
        if char == "3":
            if pos < 0:
                note = "  <- 3 is a NOP (pos < 0)"
            elif machine.ip < ip:
                note = f"  <- 3 TRUE, jumped BACK to ip={machine.ip}"
            else:
                note = f"  <- 3 FALSE, skipped FORWARD to ip={machine.ip}"
        if io.getvalue() != before:
            note += f"  PRINTS {io.getvalue()[len(before) :]!r}"
        print(f"    ip={ip} c={char} pos={pos} byte={machine.byte()}{note}")
        steps += 1
    print(f"    -> output={io.getvalue()!r} halted={machine.halted}")


def main():
    """Trace both instantiations of the selector."""
    for bit in (0, 1):
        code = TEMPLATE.replace("{X0}", SETTER[bit])
        print(f"bit={bit}  code={code!r}")
        trace(code)
        print()


if __name__ == "__main__":
    main()
