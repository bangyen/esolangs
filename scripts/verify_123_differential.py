"""Differential check of the 123 interpreter across three implementations.

Runs the same _123-generated program through the original x86 123.asm, the
RISC-V port (extra/assembly/123-riscv.s), and the Python simulator
(scripts/riscv_sim.py), and requires all three to output the source text.

Usage:
    python scripts/verify_123_differential.py <riscv-elf> <text> [<text> ...]

Requires: pip install unicorn; nasm on PATH; the RISC-V ELF built first.
"""

import sys

from riscv_elf_runner import run_elf as run_riscv
from riscv_sim import disassemble_and_run
from x86_elf_runner import assemble
from x86_elf_runner import run_elf as run_x86

from esolangs.tools.generate import _123


def main(argv):
    rv_binary = open(argv[1], "rb").read()
    x86_binary = assemble("extra/assembly/123.asm")
    failures = 0
    for text in argv[2:]:
        program = _123(text).encode()
        x86_out, _ = run_x86(x86_binary, program)
        rv_out, _ = run_riscv(rv_binary, program)
        sim_out = disassemble_and_run(rv_binary, program)
        expected = text.encode()
        ok = x86_out == expected and rv_out == expected and sim_out == expected
        failures += not ok
        if not ok:
            print(f"input {text!r}")
            print(f"  x86   -> {x86_out!r}")
            print(f"  riscv -> {rv_out!r}")
            print(f"  sim   -> {sim_out!r}")
        else:
            print(f"input {text!r} -> all three agree {expected!r}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
