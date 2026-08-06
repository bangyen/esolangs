"""Verify the x86 assembly compilers end to end.

Each compiler in src/esolangs/compilers/assembly/ translates an esolang
program to x86 assembly. This script compiles a program, assembles it with
nasm, runs the machine code under unicorn, and checks the output.

Compilers with generators (bfstack, suffolk) are round-tripped: the generated
program is compiled and must reproduce the source text. The others (home-row,
jaune, unsquare) get fixed programs with known output; unsquare additionally
round-trips its generator.

Usage:
    python scripts/verify_asm_compilers.py

Requires: pip install unicorn; nasm on PATH.
"""

import importlib
import sys

from x86_elf_runner import assemble_source, run_elf

from esolangs.tools import generate as gen

# (name, module, source program, expected output)
CASES = []
for text in ["Hi", "Hello, World!", "esolangs!"]:
    CASES.append(("bfstack", "bfstack", gen.bfstack(text), text))
    CASES.append(("suffolk", "suffolk", gen.suffolk(text), text))
    CASES.append(("unsquare", "unsquare", gen.unsquare(text), text))
CASES.append(("home-row", "home-row", "a" * 65 + "k;", "A"))
CASES.append(("jaune", "jaune", "6+5+^.", "11"))
CASES.append(("unsquare", "unsquare", "IA" + "+" * 32 + "Po", "A"))


def main(argv):
    failures = 0
    for name, module, source, expected in CASES:
        comp = importlib.import_module(f"esolangs.compilers.assembly.{module}").comp
        args = (source, 1) if module == "suffolk" else (source,)
        binary = assemble_source(comp(*args))
        out, _ = run_elf(binary, b"")
        ok = out == expected.encode()
        failures += not ok
        print(f"{name}: {'ok' if ok else 'FAIL'} -> {out!r}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
