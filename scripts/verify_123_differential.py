"""Differential check of the 123 interpreter across four implementations.

Runs the same _123-generated program through the original x86 123.asm, the
RISC-V port (extra/assembly/123-riscv.s), the Python simulator
(scripts/riscv_sim.py), and the in-package Python interpreter
(esolangs.interpreters.tape_based.123), and requires all four to output the
source text.

Usage:
    python scripts/verify_123_differential.py <riscv-elf> <text> [<text> ...]

Requires: pip install unicorn; nasm on PATH; the RISC-V ELF built first.
"""

import importlib
import sys

from riscv_elf_runner import run_elf as run_riscv
from riscv_sim import disassemble_and_run
from x86_elf_runner import assemble
from x86_elf_runner import run_elf as run_x86

from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.generate import _123

run_python = importlib.import_module("esolangs.interpreters.tape_based.123").run


def _run_python(program: bytes) -> bytes:
    """Run ``program`` through the in-package interpreter, returning bytes."""
    io = ScriptedIO("")
    run_python(program.decode(), io)
    return io.getvalue().encode()


def main(argv: list[str]) -> int:
    """Differential-test the 1/2 compiler against its interpreter."""
    with open(argv[1], "rb") as f:
        rv_binary = f.read()
    x86_binary = assemble("extra/assembly/123.asm")
    failures = 0
    for text in argv[2:]:
        program = _123(text).encode()
        x86_out, _ = run_x86(x86_binary, program)
        rv_out, _ = run_riscv(rv_binary, program)
        sim_out = disassemble_and_run(rv_binary, program)
        py_out = _run_python(program)
        expected = text.encode()
        ok = (
            x86_out == expected
            and rv_out == expected
            and sim_out == expected
            and py_out == expected
        )
        failures += not ok
        if not ok:
            print(f"input {text!r}")
            print(f"  x86    -> {x86_out!r}")
            print(f"  riscv  -> {rv_out!r}")
            print(f"  sim    -> {sim_out!r}")
            print(f"  python -> {py_out!r}")
        else:
            print(f"input {text!r} -> all four agree {expected!r}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
