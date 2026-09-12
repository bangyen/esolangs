"""Shared test helpers for the OISC (one-instruction) interpreters.

AddSubJump and Decleq both run a self-modifying flat memory of integers, so
their tests build the initial-memory string and drive the interpreter the
same way.
"""

import contextlib

from esolangs.interpreters.io import ScriptedIO


def memory(instructions, cells=None):
    """Build the initial-memory code string.

    ``instructions`` is a list of operand lists (one per instruction);
    ``cells`` maps extra memory addresses to their initial values (the
    self-modifying model stores the program and data in one flat memory).
    """
    mem = []
    for ins in instructions:
        mem.extend(ins)
    cells = cells or {}
    while len(mem) <= max(cells, default=-1):
        mem.append(0)
    for addr, value in cells.items():
        mem[addr] = value
    return " ".join(map(str, mem))


def run_program(run, code, stdin=""):
    """Run ``code`` through ``run`` (the interpreter's ``run``) and return output."""
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()
