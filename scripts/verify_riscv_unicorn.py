"""Verify RISC-V machine code under unicorn: compilers and cross-check interpreters.

Two kinds of round-trip run esolang programs as RISC-V ELF under unicorn:

1. each assembly compiler in ``src/esolangs/compilers/`` translates an
   esolang program to RISC-V assembly, which is compiled and run;
2. text generators whose interpreters live in ``extra/assembly/`` feed the
   generated program to the cross-check machine code;
3. fixed programs whose expected output pins the cross-check interpreters
   without a text generator.

All three must reproduce the expected output.

Usage:
    python scripts/verify_riscv_unicorn.py

Requires: pip install unicorn; a RISC-V cross-compiler on PATH
(riscv64-linux-gnu-gcc or riscv64-elf-gcc).
"""

import importlib
import sys

from riscv_elf_runner import assemble_source, run_elf

from esolangs.tools import boolean as gen_bool
from esolangs.tools import text as gen

# Forbin has no text generator (its output alphabet is whole bytes built
# from eight bit arguments), so its text case is the repo's own example.
with open("examples/hello-world/forbin.txt") as _f:
    _FORBIN_HELLO = _f.read()

# Generators whose cross-check interpreter lives in extra/assembly/: the
# generated program must reproduce its text when run as machine code.
REFERENCE_TEXTS = ["Hi", "Hello, World!", "esolangs!", "A\nB", "\x00"]
GENERATOR_CASES = [
    ("nocomment", "extra/assembly/nocomment-riscv.s", gen.nocomment),
]

# Fixed programs for the cross-check interpreters without a text generator:
# each must reproduce its expected output (and exit code) as machine code.
REFERENCE_CASES = [
    ("bfpda", "extra/assembly/bfpda-riscv.s", "<.>@.", "01"),
    ("bfpda", "extra/assembly/bfpda-riscv.s", "<@.", "1"),
    ("bfpda", "extra/assembly/bfpda-riscv.s", "<@<@[.>]", "11"),
    ("ram0", "extra/assembly/ram0-riscv.s", "A A A", "z: 3\nn: 0\nram: {}"),
    (
        "ram0",
        "extra/assembly/ram0-riscv.s",
        "A A N A A A S",
        "z: 5\nn: 2\nram: {\n    2: 5\n}",
    ),
    ("ram0", "extra/assembly/ram0-riscv.s", "A 3 A A", "z: 3\nn: 0\nram: {}"),
    ("bio", "extra/assembly/bio-riscv.s", "0ox;0ox;0ox;1ix;", "\x03"),
    (
        "bio",
        "extra/assembly/bio-riscv.s",
        "0ox;0ix{0oy;1ox;};1iy;",
        "\x01",
    ),
    (
        "bio",
        "extra/assembly/bio-riscv.s",
        "0ox;" * 66 + "1ix;",
        "B",
    ),
    ("minsky_swap", "extra/assembly/minsky_swap-riscv.s", "+++~\n1", "2 0"),
    ("minsky_swap", "extra/assembly/minsky_swap-riscv.s", "++*++*+++", "5 2"),
    (
        "minsky_swap",
        "extra/assembly/minsky_swap-riscv.s",
        "+++*+++*~+~\n2 1",
        "2 3",
    ),
]

# (name, compiler module, source program, expected output[, stdin]).
# Compilers with generators (bfstack, suffolk, unsquare, home_row)
# round-trip them; the others (jaune, bf_pda, ram0) get fixed programs with
# known output.  Forbin and Container read stdin, so their boolean cases
# carry a fifth element; everything else runs on empty input.
COMPILER_CASES: list[tuple[str, str, str, str] | tuple[str, str, str, str, str]] = []
for text in ["Hi", "Hello, World!", "esolangs!"]:
    COMPILER_CASES.append(("bfstack", "bfstack", gen.bfstack(text), text))
    COMPILER_CASES.append(("suffolk", "suffolk", gen.suffolk(text), text))
    COMPILER_CASES.append(("unsquare", "unsquare", gen.unsquare(text), text))
    COMPILER_CASES.append(("home_row", "home_row", gen.home_row(text), text))
    COMPILER_CASES.append(("addsubjump", "addsubjump", gen.addsubjump(text), text))
    COMPILER_CASES.append(
        ("collatz_multiverse", "collatz_multiverse", gen.collatz_multiverse(text), text)
    )
    COMPILER_CASES.append(("sbleq", "sbleq", gen.sbleq(text), text))
    COMPILER_CASES.append(("decleq", "decleq", gen.decleq(text), text))
    COMPILER_CASES.append(("container", "container", gen.container(text), text))
    COMPILER_CASES.append(("cvnc", "cvnc", gen.cvnc(text), text))
COMPILER_CASES.append(("home_row", "home_row", "a" * 65 + "k;", "A"))
COMPILER_CASES.append(("jaune", "jaune", "6+5+^.", "11"))
COMPILER_CASES.append(("unsquare", "unsquare", "IA" + "+" * 32 + "Po", "A"))
COMPILER_CASES.append(("bf_pda", "bf_pda", "<.>@.", "01"))
COMPILER_CASES.append(("ram0", "ram0", "A A A", "z: 3\nn: 0\nram: {}"))
COMPILER_CASES.append(("ram0", "ram0", "A A N S", "z: 2\nn: 2\nram: {\n    2: 2\n}"))
COMPILER_CASES.append(("forth", "forth", "65.", "\x05"))
COMPILER_CASES.append(("forth", "forth", "5:..", "\x05\x05"))
COMPILER_CASES.append(("forth", "forth", "28*.", "\x10"))
COMPILER_CASES.append(("forth", "forth", "09/~.", "\xff"))
COMPILER_CASES.append(("forth", "forth", "1(F4*5+.)", "A"))
COMPILER_CASES.append(("forth", "forth", "0F7*0+F4*C+[.]", "Hi"))
COMPILER_CASES.append(("forth", "forth", "1{F4*5+.}1;", "A"))
COMPILER_CASES.append(("forth", "forth", "1{/}1;", ""))
# Forbin: the text example, then the boolean generator's AND2 program run
# over its whole input space.  Forbin's `in` is line-faithful (IO.input_char
# takes one byte per line), so each input bit is its own line.
_FORBIN_AND2 = gen_bool.forbin_boolean("0001")
COMPILER_CASES.append(("forbin", "forbin", _FORBIN_HELLO, "Hello, World!"))
for _a in "01":
    for _b in "01":
        COMPILER_CASES.append(
            (
                "forbin",
                "forbin",
                _FORBIN_AND2,
                "1" if _a == "1" and _b == "1" else "0",
                f"{_a}\n{_b}",
            )
        )
# Container: the boolean generator's AND2 program over its whole input
# space.  Container's reader drains a *line* one character per pulse, so
# unlike Forbin the bits could share a line; they are written one per line
# to match the block above, and both spellings run identically.
_CONTAINER_AND2 = gen_bool.container("0001")
for _a in "01":
    for _b in "01":
        COMPILER_CASES.append(
            (
                "container",
                "container",
                _CONTAINER_AND2,
                "1" if _a == "1" and _b == "1" else "0",
                f"{_a}\n{_b}",
            )
        )
# CV(N)(C): the boolean generator's AND2 program over its whole input
# space.  Its read is `s`, which parses a whole *line* as an integer, so
# each bit is its own line -- and unlike the two blocks above that is
# forced rather than a matching convention: two bits on one line would
# parse as a single two-digit number.
_CVNC_AND2 = gen_bool.cvnc("0001")
for _a in "01":
    for _b in "01":
        COMPILER_CASES.append(
            (
                "cvnc",
                "cvnc",
                _CVNC_AND2,
                "1" if _a == "1" and _b == "1" else "0",
                f"{_a}\n{_b}\n",
            )
        )
_CM_CONSTANTS = "\n".join(
    [
        "one = negativeOne x + negativeOne, NOT PRINT.",
        "one = negativeOne x + zero, NOT PRINT.",
        "two = negativeOne x + negativeOne, NOT PRINT.",
        "two = negativeOne x + one, NOT PRINT.",
        "three = negativeOne x + one, NOT PRINT.",
        "three = one x + two, NOT PRINT.",
    ]
)
COMPILER_CASES.append(
    (
        "collatz_multiverse",
        "collatz_multiverse",
        _CM_CONSTANTS
        + "\n".join(
            [
                "",
                "lineNumber = one x + two, NOT PRINT.",
                "x = negativeOne x + zero, DO PRINT.",
                "arr[negativeOne] = negativeOne x + one, NOT PRINT.",
                "x = negativeOne x + arr[negativeOne], DO PRINT.",
            ]
        ),
        "\x01",
    )
)


def main() -> int:
    """Verify the RISC-V compilers under Unicorn, reporting failures."""
    failures = 0
    for name, path, generator in GENERATOR_CASES:
        with open(path) as f:
            binary = assemble_source(f.read())
        for text in REFERENCE_TEXTS:
            out, _ = run_elf(binary, generator(text).encode())
            ok = out == text.encode("latin-1")
            failures += not ok
            print(f"{name} {text!r}: {'ok' if ok else 'FAIL'} -> {out!r}")
    for name, path, program, expected in REFERENCE_CASES:
        with open(path) as f:
            binary = assemble_source(f.read())
        out, code = run_elf(binary, program.encode())
        ok = out == expected.encode("latin-1") and code == 0
        failures += not ok
        print(f"{name}: {'ok' if ok else 'FAIL'} -> {out!r} (exit {code})")
    for name, module, source, expected, *rest in COMPILER_CASES:
        comp = importlib.import_module(f"esolangs.compilers.{module}").comp
        args = (source, 1) if module == "suffolk" else (source,)
        binary = assemble_source(comp(*args))
        stdin = rest[0].encode("latin-1") if rest else b""
        out, _ = run_elf(binary, stdin)
        # latin-1: one byte per expected char; UTF-8 would expand 0x80+ to
        # multi-byte and never match a single-byte machine-code output.
        ok = out == expected.encode("latin-1")
        failures += not ok
        print(f"{name}: {'ok' if ok else 'FAIL'} -> {out!r}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
