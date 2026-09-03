"""Compiler that turns Suffolk programs into RISC-V Linux assembly."""

import sys
from re import sub

from esolangs.compilers._riscv_common import MUL32, Routine


def count(code: str, ind: int) -> int:
    """Return the run length of the command at ``ind``."""
    char = code[ind]
    code += " "
    num = 0

    while code[ind] == char:
        num += 1
        ind += 1

    return num


def comp(code: str, num: int = 1) -> str:
    """Compile a Suffolk program to RISC-V assembly, looping ``num`` times.

    ``num`` defaults to one so that ``comp(code)`` is callable exactly as
    every other compiler in this package is; a driver iterating the
    compilers then needs no special case for this one.
    """
    code = sub("[^><.,!]", "", code)
    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        f"    li   s4, {num}\n"
        "    li   s3, 0\n"
        "    addi s1, sp, -12\n"
        "    addi s2, s1, -4\n"
        "    li   s5, 1\n"
        ".main:\n"
    )
    length = len(code)

    ind = 0
    # The four helper subroutines, gated so a program carries only the
    # ones it calls -- the shared `Routine` the other tape compilers use.
    subr = {
        "left": Routine("left"),
        "input": Routine("input"),
        "output": Routine("output"),
        "excl": Routine("excl"),
    }

    while ind < length:
        n = count(code, ind)
        c = code[ind]

        if c == ">":
            s = f"li   t0, {n * 4}\n\tsub  s2, s2, t0"
        elif c == "<":
            s = "lw   t0, 0(s2)\n\tadd  s3, s3, t0\n\taddi s2, s1, -4"

            if n > 2:
                s += f"\n\tli   s5, {n - 1}\n\tcall left"
            elif n == 2:
                s += "\n\tlw   t0, 0(s2)\n\tadd  s3, s3, t0"

            subr["left"].used = True
        elif c == ".":
            s = "output"
            subr["output"].used = True
        elif c == ",":
            s = "input"
            subr["input"].used = True
        else:
            s = "call excl"
            if n > 1:
                s += f"\n\tlw   t0, 0(s2)\n\taddi t0, t0, {n - 1}\n\tsw   t0, 0(s2)"
            subr["excl"].used = True

        if c in ".,":
            s = "\n\t".join(f"call {s}" for _ in range(n))
        res += f"\t{s}\n"

        ind += n

    res += (
        "\n\taddi s4, s4, -1\n"
        "\tbgt  s4, zero, .main\n"
        "\tli   a0, 0\n"
        "\tli   a7, 93\n"
        "\tecall"
    )

    if subr["input"].used:
        res += (
            "\n\ninput:\n"
            "\tli   a7, 63\n"
            "\tli   a0, 0\n"
            "\tmv   a1, s1\n"
            "\tli   a2, 1\n"
            "\tecall\n"
            "\tlw   t0, 0(s1)\n"
            "\tadd  s3, s3, t0\n"
            "\tret"
        )
    if subr["output"].used:
        res += (
            "\n\noutput:\n"
            "\tbeqz s3, .output_done\n"
            "\taddi s3, s3, -1\n"
            "\tsw   s3, 0(s1)\n"
            "\tli   a7, 64\n"
            "\tli   a0, 1\n"
            "\tmv   a1, s1\n"
            "\tli   a2, 1\n"
            "\tecall\n"
            "\taddi s3, s3, 1\n"
            ".output_done:\n"
            "\tret"
        )
    if subr["excl"].used:
        res += (
            "\n\nexcl:\n"
            "\tlw   t0, 0(s2)\n"
            "\taddi t0, t0, 1\n"
            "\tsub  t0, t0, s3\n"
            "\tbge  t0, zero, .excl_done\n"
            "\tli   t0, 0\n"
            ".excl_done:\n"
            "\tsw   t0, 0(s2)\n"
            "\tli   s3, 0\n"
            "\taddi s2, s1, -4\n"
            "\tret"
        )
    if subr["left"].used:
        res += (
            "\n\nleft:\n"
            "\taddi sp, sp, -16\n"
            "\tsd   ra, 8(sp)\n"
            "\tlw   a0, 0(s2)\n"
            "\tmv   a1, s5\n"
            "\tcall mul32\n"
            "\tadd  s3, s3, a0\n"
            "\tli   s5, 1\n"
            "\tld   ra, 8(sp)\n"
            "\taddi sp, sp, 16\n"
            "\tret\n"
            "\n" + MUL32
        )

    return res


if __name__ == "__main__":
    loop = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data, loop))
