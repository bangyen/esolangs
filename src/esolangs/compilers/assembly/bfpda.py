"""Compiler that turns BF-PDA programs into RISC-V Linux assembly."""

import sys


def comp(code: str) -> str:
    """Compile a BF-PDA program to RISC-V assembly with syscall I/O.

    The bit stack lives on the stack with the top at ``s1``, growing down on
    ``<`` (push) and up on ``>`` (pop).  ``@`` flips the top bit and ``.``
    prints it as ``'0'``/``'1'``.  Per the interpreter's Lean-ported
    semantics, ``[``/``]`` advance past themselves (a matched pair runs its
    body once), so they compile to nothing.
    """
    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    addi sp, sp, -64\n"
        "    addi s1, sp, 64\n"
    )
    for ch in code:
        if ch == "<":
            res += "\taddi s1, s1, -1\n\tsb   zero, 0(s1)\n"
        elif ch == ">":
            res += "\taddi s1, s1, 1\n"
        elif ch == "@":
            res += "\tlbu  t0, 0(s1)\n\txori t0, t0, 1\n\tsb   t0, 0(s1)\n"
        elif ch == ".":
            res += (
                "\tlbu  t0, 0(s1)\n"
                "\taddi t0, t0, 48\n"
                "\tsb   t0, 0(sp)\n"
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
