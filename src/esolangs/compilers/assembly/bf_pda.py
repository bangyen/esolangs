"""Compiler that turns BF-PDA programs into RISC-V Linux assembly."""

import sys


def comp(code: str) -> str:
    """Compile a BF-PDA program to RISC-V assembly with syscall I/O.

    The bit stack lives on the stack with the top at ``s1`` (growing down on
    ``<``, up on ``>``) and the base at ``s2``, so an empty stack reads as 0
    per the wiki.  ``@`` flips the top bit (pushing and flipping a fresh 1 on
    an empty stack), ``.`` prints it as ``'0'``/``'1'``, and ``[``/``]`` are
    while loops that re-check the top each pass.
    """
    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    addi sp, sp, -64\n"
        "    addi s1, sp, 64\n"
        "    mv   s2, s1\n"
    )
    loops: list[int] = []
    label = 0
    for ch in code:
        if ch == "<":
            res += "\taddi s1, s1, -1\n\tsb   zero, 0(s1)\n"
        elif ch == ">":
            res += f"\tbge  s1, s2, .p{label}\n\taddi s1, s1, 1\n.p{label}:\n"
            label += 1
        elif ch == "@":
            res += (
                f"\tbge  s1, s2, .a{label}\n"
                "\tlbu  t0, 0(s1)\n"
                "\txori t0, t0, 1\n"
                "\tsb   t0, 0(s1)\n"
                f"\tj .d{label}\n"
                f".a{label}:\n"
                "\taddi s1, s1, -1\n"
                "\tli   t0, 1\n"
                "\tsb   t0, 0(s1)\n"
                f".d{label}:\n"
            )
            label += 1
        elif ch == ".":
            res += (
                f"\tbge  s1, s2, .e{label}\n"
                "\tlbu  t0, 0(s1)\n"
                f"\tj .f{label}\n"
                f".e{label}:\n"
                "\tli   t0, 0\n"
                f".f{label}:\n"
                "\taddi t0, t0, 48\n"
                "\tsb   t0, 0(sp)\n"
                "\tli   a7, 64\n"
                "\tli   a0, 1\n"
                "\tmv   a1, sp\n"
                "\tli   a2, 1\n"
                "\tecall\n"
            )
            label += 1
        elif ch == "[":
            res += (
                f".T{label}:\n"
                f"\tbge  s1, s2, .B{label}\n"
                "\tlbu  t0, 0(s1)\n"
                f"\tbeqz t0, .B{label}\n"
            )
            loops.append(label)
            label += 1
        elif ch == "]" and loops:
            m = loops.pop()
            res += f"\tj .T{m}\n.B{m}:\n"
    res += "\tli   a0, 0\n\tli   a7, 93\n\tecall\n"
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data))
