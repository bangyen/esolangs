"""Verify x86 machine code under unicorn: compilers and reference interpreters.

Two kinds of round-trip run esolang programs as x86 ELF under unicorn:

1. each assembly compiler in ``src/esolangs/compilers/assembly/`` translates
   an esolang program to x86 assembly, which is assembled with nasm and run;
2. text generators whose interpreters live in ``extra/assembly/`` feed the
   generated program to the reference machine code.

Both must reproduce the expected output.

Usage:
    python scripts/verify_x86_unicorn.py

Requires: pip install unicorn; nasm on PATH.
"""

import importlib
import sys

from x86_elf_runner import assemble, assemble_source, run_elf

from esolangs.tools import generate as gen

# Generators whose reference interpreter lives in extra/assembly/: the
# generated program must reproduce its text when run as machine code.
REFERENCE_TEXTS = ["Hi", "Hello, World!", "esolangs!", "A\nB", "\x00"]
GENERATOR_CASES = [
    ("nocomment", "extra/assembly/nocomment.asm", gen.nocomment),
]

# (name, compiler module, source program, expected output).  Compilers with
# generators (bfstack, suffolk) round-trip them; the others (home-row, jaune,
# unsquare) get fixed programs with known output.
COMPILER_CASES = []
for text in ["Hi", "Hello, World!", "esolangs!"]:
    COMPILER_CASES.append(("bfstack", "bfstack", gen.bfstack(text), text))
    COMPILER_CASES.append(("suffolk", "suffolk", gen.suffolk(text), text))
    COMPILER_CASES.append(("unsquare", "unsquare", gen.unsquare(text), text))
    COMPILER_CASES.append(("home-row", "home-row", gen.home_row(text), text))
COMPILER_CASES.append(("home-row", "home-row", "a" * 65 + "k;", "A"))
COMPILER_CASES.append(("jaune", "jaune", "6+5+^.", "11"))
COMPILER_CASES.append(("unsquare", "unsquare", "IA" + "+" * 32 + "Po", "A"))


def main() -> int:
    failures = 0
    for name, path, generator in GENERATOR_CASES:
        binary = assemble(path)
        for text in REFERENCE_TEXTS:
            out, _ = run_elf(binary, generator(text).encode())
            ok = out == text.encode()
            failures += not ok
            print(f"{name} {text!r}: {'ok' if ok else 'FAIL'} -> {out!r}")
    for name, module, source, expected in COMPILER_CASES:
        comp = importlib.import_module(f"esolangs.compilers.assembly.{module}").comp
        args = (source, 1) if module == "suffolk" else (source,)
        binary = assemble_source(comp(*args))
        out, _ = run_elf(binary, b"")
        ok = out == expected.encode()
        failures += not ok
        print(f"{name}: {'ok' if ok else 'FAIL'} -> {out!r}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
