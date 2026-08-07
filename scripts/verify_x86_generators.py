"""Round-trip generators whose interpreters live in extra/assembly/.

Some text generators produce programs for interpreters that only exist as
x86 assembly in extra/assembly/. This script feeds the generated program to
the real interpreter machine code (assembled with nasm, run under unicorn)
and checks that the output reproduces the source text.

Usage:
    python scripts/verify_x86_generators.py

Requires: pip install unicorn; nasm on PATH.
"""

import sys

from x86_elf_runner import assemble, run_elf

from esolangs.tools import generate as gen

TEXTS = ["Hi", "Hello, World!", "esolangs!", "A\nB", "\x00"]

CASES = [
    ("nocomment", "extra/assembly/nocomment.asm", gen.nocomment),
]


def main(argv: list[str]) -> int:
    failures = 0
    for name, path, generator in CASES:
        binary = assemble(path)
        for text in TEXTS:
            out, _ = run_elf(binary, generator(text).encode())
            ok = out == text.encode()
            failures += not ok
            print(f"{name} {text!r}: {'ok' if ok else 'FAIL'} -> {out!r}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
