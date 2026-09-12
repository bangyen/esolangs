r"""Shared test helpers for the OISC (one-instruction) interpreters."""

import contextlib

from esolangs.interpreters.io import ScriptedIO


def memory(instructions, cells=None):
    r"""Build the initial-memory code string."""
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
    r"""Run ``code`` through ``run`` (the interpreter's ``run``) and return."""
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()
