"""Differential check of the 123 interpreter across three implementations.

Runs the same _123-generated program through the RISC-V port
(extra/assembly/123-riscv.s), the Python simulator (scripts/riscv_sim.py),
and the in-package Python interpreter (esolangs.interpreters.tape_based.one_two_three),
and requires all three to output the source text.  Hand-written programs
exercising the ``3`` jump paths (which the generator never emits) are
checked the same way against their expected output.

Usage:
    python scripts/verify_123_differential.py <riscv-elf> <text> [<text> ...]

Requires: pip install unicorn; the RISC-V ELF built first.
"""

import importlib
import sys

from riscv_elf_runner import run_elf as run_riscv
from riscv_sim import disassemble_and_run

from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.generate import _123

run_python = importlib.import_module(
    "esolangs.interpreters.tape_based.one_two_three"
).run

# Hand-written programs exercising the 3 jump paths, with expected output.
# 3231: a FALSE 3 skips to the next 3, then a 1 leaves the pointer below 0.
# 132231: a FALSE 3 reaches the end of the program, the program restarts, and
# only then halts -- the fixed FALSE-to-end path in the assembly ports.
# Looping FALSE-to-end programs are excluded: they never halt, which the
# expected-output form cannot express.
HAND_WRITTEN = (
    ("3231", b""),
    ("132231", b""),
)


def _run_python(program: bytes) -> bytes:
    """Run ``program`` through the in-package interpreter, returning bytes."""
    io = ScriptedIO("")
    run_python(program.decode(), io)
    return io.getvalue().encode()


def main(argv: list[str]) -> int:
    """Differential-test the 1/2 compiler against its interpreter."""
    with open(argv[1], "rb") as f:
        rv_binary = f.read()
    failures = 0

    def check(program: bytes, expected: bytes, label: str) -> None:
        nonlocal failures
        rv_out, _ = run_riscv(rv_binary, program)
        sim_out = disassemble_and_run(rv_binary, program)
        py_out = _run_python(program)
        ok = rv_out == expected and sim_out == expected and py_out == expected
        failures += not ok
        if not ok:
            print(f"input {label!r}")
            print(f"  riscv  -> {rv_out!r}")
            print(f"  sim    -> {sim_out!r}")
            print(f"  python -> {py_out!r}")
        else:
            print(f"input {label!r} -> all three agree {expected!r}")

    for text in argv[2:]:
        check(_123(text).encode(), text.encode(), text)
    for program, expected in HAND_WRITTEN:
        check(program.encode(), expected, program)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
