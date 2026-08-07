"""Verify the RISC-V 123 interpreter under unicorn (an independent emulator).

Generates the _123 program for each text, runs it through the interpreter ELF
with scripts/riscv_elf_runner.py, and checks that the output matches.

Usage:
    python scripts/verify_123_unicorn.py <elf> <text> [<text> ...]

Requires: pip install unicorn
"""

import sys

from riscv_elf_runner import run_elf

from esolangs.tools.generate import _123


def main(argv):
    with open(argv[1], "rb") as f:
        binary = f.read()
    failures = 0
    for text in argv[2:]:
        out, _ = run_elf(binary, _123(text).encode())
        ok = out == text.encode()
        failures += not ok
        print(f"input {text!r} -> output {out!r} {'ok' if ok else 'FAIL'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
