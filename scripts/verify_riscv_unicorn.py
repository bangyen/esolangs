"""Verify RISC-V machine code under unicorn: compilers and cross-check interpreters.

Two kinds of round-trip run esolang programs as RISC-V ELF under unicorn:

1. each assembly compiler in ``src/esolangs/compilers/assembly/`` translates
   an esolang program to RISC-V assembly, which is compiled and run;
2. text generators whose interpreters live in ``extra/assembly/`` feed the
   generated program to the cross-check machine code.

Both must reproduce the expected output.

Usage:
    python scripts/verify_riscv_unicorn.py

Requires: pip install unicorn; a RISC-V cross-compiler on PATH
(riscv64-linux-gnu-gcc or riscv64-elf-gcc).
"""

import importlib
import sys

from riscv_elf_runner import assemble_source, run_elf

from esolangs.tools import generate as gen

# Generators whose cross-check interpreter lives in extra/assembly/: the
# generated program must reproduce its text when run as machine code.
REFERENCE_TEXTS = ["Hi", "Hello, World!", "esolangs!", "A\nB", "\x00"]
GENERATOR_CASES = [
    ("nocomment", "extra/assembly/nocomment-riscv.s", gen.nocomment),
]

# (name, compiler module, source program, expected output).  Compilers with
# generators (bfstack, suffolk, unsquare, home_row, excon) round-trip them;
# the others (jaune, bf_pda, ram0) get fixed programs with known output.
COMPILER_CASES = []
for text in ["Hi", "Hello, World!", "esolangs!"]:
    COMPILER_CASES.append(("bfstack", "bfstack", gen.bfstack(text), text))
    COMPILER_CASES.append(("suffolk", "suffolk", gen.suffolk(text), text))
    COMPILER_CASES.append(("unsquare", "unsquare", gen.unsquare(text), text))
    COMPILER_CASES.append(("home_row", "home_row", gen.home_row(text), text))
    COMPILER_CASES.append(("excon", "excon", gen.excon(text), text))
COMPILER_CASES.append(("home_row", "home_row", "a" * 65 + "k;", "A"))
COMPILER_CASES.append(("jaune", "jaune", "6+5+^.", "11"))
COMPILER_CASES.append(("unsquare", "unsquare", "IA" + "+" * 32 + "Po", "A"))
COMPILER_CASES.append(("bf_pda", "bf_pda", "<.>@.", "01"))
COMPILER_CASES.append(("ram0", "ram0", "A A A", "z: 3\nn: 0\nram: {}\n"))
COMPILER_CASES.append(("ram0", "ram0", "A A N S", "z: 2\nn: 2\nram: {\n    2: 2\n}\n"))


def main() -> int:
    """Verify the RISC-V compilers under Unicorn, reporting failures."""
    failures = 0
    for name, path, generator in GENERATOR_CASES:
        with open(path) as f:
            binary = assemble_source(f.read())
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
