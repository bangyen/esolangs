"""Compiler that turns EXCON programs into RISC-V Linux assembly."""

import sys


def comp(code: str) -> str:
    """Compile an EXCON program to straight-line RISC-V assembly.

    The 8-cell bit pool lives in ``s1`` (pool[0] is the MSB) and the pointer
    in ``s2``, so ``^`` at cell ``c`` flips bit ``7 - c`` of ``s1`` and ``!``
    writes the byte to stdout.
    """
    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    addi sp, sp, -16\n"
        "    li   s1, 0\n"
        "    li   s2, 7\n"
    )
    for ch in code:
        if ch == ":":
            res += "\tli   s1, 0\n\tli   s2, 7\n"
        elif ch == "^":
            res += (
                "\tli   t0, 7\n"
                "\tsub  t0, t0, s2\n"
                "\tli   t1, 1\n"
                "\tsll  t1, t1, t0\n"
                "\txor  s1, s1, t1\n"
            )
        elif ch == "<":
            res += "\taddi s2, s2, -1\n"
        elif ch == "!":
            res += (
                "\tsb   s1, 0(sp)\n"
                "\tli   a7, 64\n"
                "\tli   a0, 1\n"
                "\tmv   a1, sp\n"
                "\tli   a2, 1\n"
                "\tecall\n"
            )
    res += "\tli   a0, 0\n\tli   a7, 93\n\tecall\n"
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data))
