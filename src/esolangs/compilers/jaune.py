"""Compiler that turns Jaune programs into RISC-V Linux assembly.

Compiled Jaune programs read one character per input operation, so a
program can only input a single character at a time.
"""

import sys
from re import findall, sub
from typing import Literal

from esolangs.compilers._riscv_common import MUL32, Routine

# The four commands that compile to a called subroutine rather than to
# inline instructions.
_Subr = Literal["^", "v", "<", "&"]

# The three that dispatch through the shared table below; "&" is
# handled by its own arm.  Typed so the membership test narrows the
# command to the key type rather than asserting it afterwards.
_CALLED: frozenset[_Subr] = frozenset(("^", "v", "<"))


def count(code: str, ind: int) -> tuple[int | str, int]:
    """Return the operand value at ``ind`` and the next index.

    Handles run-lengths, signed ``+``/``-`` operands, and the marker commands
    ``: $ @ ? !`` whose operand is the preceding character.
    """

    def check(k: int, s: str) -> bool:
        ch = code[k]
        return ch.isnumeric() or ch in s

    start = code[ind]
    code += " "
    num = 0

    if start in "+-":
        if (n := code[ind - 1]).isnumeric():
            num = int(start + code[ind - 1])
            while check(ind, "+-"):
                x, y = code[ind], code[ind + 1]
                if x.isnumeric() and y in "+-":
                    num += int(y + x)
                ind += 1
        else:
            return n, ind + 1
    elif start in ":$@?!":
        num = -1 if (c := code[ind - 1]) == "v" else int(c) if c.isdigit() else -1
        ind += 1
    else:
        while code[ind] == start:
            num += 1
            ind += 1

    return num, ind


def prep(code: str) -> tuple[str, list[int], list[int]]:
    """Filter to the command alphabet and assign labels to jumps/routines."""

    def rep(sym: str) -> str:
        return sub(r"\d[?!]", "", sym)

    code = sub(r"[^^v><\d+\-#&:?!.$@;%]", "", code)
    code = sub(r"([#.;%])\1+", r"\1", code)
    code = sub("v[:$]", "", code)

    jump: list[int] = []
    rout: list[int] = []

    for c in ":$":
        esc = "\\$" if c == "$" else c
        r = rf"(?:[\d]{esc})+"
        for s in findall(r, code):
            lst = [k for k in s if k.isnumeric()]
            num = jump if c == ":" else rout
            opr = "?!" if c == ":" else "@"

            plus = num[-1] + 1 if num else 0
            num.append(plus)
            m = str(plus)

            for n in lst:
                for k in opr:
                    code = code.replace(n + k, m + k)

            code = code.replace(s, m + c)

    for s in findall(r"(?:[v\d][?!]){2,}", code):
        if "?" in s and "!" in s:
            n = s.find("!") if s[1] == "?" else s.find("?")

            repl = s[:2] + rep(s[2 : n - 1]) + s[n - 1 : n + 1] + rep(s[n + 1 :])
        else:
            repl = s[:2] + rep(s[2:])

        code = code.replace(s, repl)

    return code, jump, rout


def comp(code: str) -> str:
    """Compile a Jaune program to RISC-V assembly with decimal output."""

    def add(m: int) -> str:
        return str(m + 1) if m else ""

    code, jump, rout = prep(code)
    inp = [False, False]
    ind = 0

    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    addi s1, sp, -60\n"
        "    li   s2, 0\n"
        "    li   s3, 1\n"
        "    li   s7, 0\n\n"
    )
    subr: dict[_Subr, Routine] = {
        "^": Routine("output"),
        "v": Routine("input"),
        "<": Routine("left"),
        "&": Routine("mult"),
    }

    while ind < len(code):
        c = code[ind]
        num, new = count(code, ind)

        # ``+``/``-`` is the only command whose operand can be a bare ``v``,
        # which ``count`` reports as a str; taking that arm first leaves
        # ``num`` narrowed to int for every command below.
        if c in "+-":
            if num:
                if isinstance(num, int):
                    res += f"\tlw   t0, 0(s1)\n\taddi t0, t0, {num}\n\tsw   t0, 0(s1)\n"
                elif c == "+":
                    res += "\tlw   t0, 0(s1)\n\tadd  t0, t0, s7\n\tsw   t0, 0(s1)\n"
                else:
                    res += "\tlw   t0, 0(s1)\n\tsub  t0, t0, s7\n\tsw   t0, 0(s1)\n"
            ind = new
            continue

        if isinstance(num, str):  # pragma: no cover - see the comment above
            raise ValueError(f"unexpected operand {num!r} for {c!r}")

        if c in _CALLED:
            routine = subr[c]
            if num > 1:
                res += f"\tli   s3, {num}\n"
                routine.looped = True
            res += f"\tcall {routine.label}\n"
            routine.used = True
        elif c == "&":
            if num > 1:
                res += f"\tli   s3, {num}\n\tcall {subr['&'].label}\n"
                subr["&"].used = subr["&"].looped = True
            else:
                res += "\tlw   t0, 0(s1)\n\tadd  t0, t0, s2\n\tsw   t0, 0(s1)\n"
        elif c == ">":
            res += f"\tli   t0, {4 * num}\n\tsub  s1, s1, t0\n"
        elif c == "#":
            res += "\tlw   s2, 0(s1)\n"
        elif c == ":":
            res += f".label{add(num)}:\n"
        elif c in "?!":
            res += "\tlw   t0, 0(s1)\n"
            jcc = "bnez" if c == "?" else "beqz"
            if num >= 0:
                res += f"\t{jcc} t0, .label{add(num)}\n"
            else:
                res += f"\t{jcc} t0, .switch\n"
                inp[0] = True
        elif c == ".":
            res += "\n\tli   a0, 0\n\tli   a7, 93\n\tecall\n"
        elif c == "$":
            res += f"sub{add(num)}:\n"
        elif c == "@":
            if num >= 0:
                res += f"\tcall sub{add(num)}\n"
            else:
                res += "\tcall switch\n"
                inp[1] = True
        elif c == ";":
            res += "\tret\n"
        elif c == "%":
            res += "\tsw   zero, 0(s1)\n"

        ind = new

    if jump and inp[0]:
        res += "\n.switch:\n"
        for k in jump[:-1]:
            res += f"\tli   t0, {k}\n\tbeq  s7, t0, .lab{add(k)}\n"
        for k in jump[::-1]:
            n = add(k)
            if k != jump[-1]:
                res += f".lab{n}:\n"
            res += f"\tj .label{n}\n"
    if rout and inp[1]:
        res += "\nswitch:\n"
        for k in rout[:-1]:
            res += f"\tli   t0, {k}\n\tbeq  s7, t0, .sub{add(k)}\n"
        res += "\tret\n"
        for k in rout[::-1]:
            n = add(k)
            if k != rout[-1]:
                res += f".sub{n}:\n"
            res += f"\tcall sub{n}\n\tret\n"

    def end(opr: _Subr) -> str:
        if subr[opr].looped:
            mul = (
                "\taddi s3, s3, -1\n"
                f"\tbgt  s3, zero, {subr[opr].label}\n"
                "\taddi s3, s3, 1\n"
                "\tret\n"
            )
        else:
            mul = "\tret\n"
        return mul

    if subr["^"].used:
        res += (
            "\noutput:\n"
            "\taddi sp, sp, -16\n"
            "\tsd   ra, 8(sp)\n"
            "\tlw   s4, 0(s1)\n"
            "\tbltz s4, .out_neg\n"
            "\tmv   t0, s4\n"
            "\tj    .out_pos\n"
            ".out_neg:\n"
            "\tli   t0, '-'\n"
            "\tsb   t0, 0(s1)\n"
            "\tcall print\n"
            "\tsub  t0, x0, s4\n"
            ".out_pos:\n"
            "\taddi sp, sp, -32\n"
            "\taddi s5, sp, 32\n"
            "\tli   s6, 0\n"
            ".out_digits:\n"
            "\tmv   a0, t0\n"
            "\tli   a1, 10\n"
            "\tcall divmod\n"
            "\tmv   t0, a0\n"
            "\taddi s5, s5, -1\n"
            "\taddi t2, a1, 48\n"
            "\tsb   t2, 0(s5)\n"
            "\taddi s6, s6, 1\n"
            "\tbnez t0, .out_digits\n"
            "\tli   a7, 64\n"
            "\tli   a0, 1\n"
            "\tmv   a1, s5\n"
            "\tmv   a2, s6\n"
            "\tecall\n"
            "\taddi sp, sp, 32\n"
            "\tsw   s4, 0(s1)\n"
            "\tld   ra, 8(sp)\n"
            "\taddi sp, sp, 16\n" + end("^") + "\nprint:\n"
            "\tli   a7, 64\n"
            "\tli   a0, 1\n"
            "\tmv   a1, s1\n"
            "\tli   a2, 1\n"
            "\tecall\n"
            "\tret\n"
            "\n"
            "# a0 / a1: quotient in a0, remainder in a1 (repeated subtraction)\n"
            "divmod:\n"
            "\tli   t0, 0\n"
            ".div_loop:\n"
            "\tbltu a0, a1, .div_done\n"
            "\tsub  a0, a0, a1\n"
            "\taddi t0, t0, 1\n"
            "\tj    .div_loop\n"
            ".div_done:\n"
            "\tmv   a1, a0\n"
            "\tmv   a0, t0\n"
            "\tret\n"
        )
    if subr["v"].used:
        res += (
            "\ninput:\n"
            "\taddi s1, s1, -4\n"
            "\tli   a7, 63\n"
            "\tli   a0, 0\n"
            "\tmv   a1, s1\n"
            "\tli   a2, 1\n"
            "\tecall\n"
            "\tlbu  s7, 0(s1)\n"
            "\taddi s7, s7, -48\n"
            "\taddi s1, s1, 4\n" + end("v")
        )
    if subr["<"].used:
        res += (
            "\nleft:\n"
            "\tslli t0, s3, 2\n"
            "\tadd  s1, s1, t0\n"
            "\taddi t1, sp, -48\n"
            "\tbge  t1, s1, .left_done\n"
            "\tmv   s1, t1\n"
            ".left_done:\n"
            "\tret\n"
        )
    if subr["&"].used:
        res += (
            "\nmult:\n"
            "\taddi sp, sp, -16\n"
            "\tsd   ra, 8(sp)\n"
            "\tmv   a0, s2\n"
            "\tmv   a1, s3\n"
            "\tcall mul32\n"
            "\tlw   t0, 0(s1)\n"
            "\tadd  t0, t0, a0\n"
            "\tsw   t0, 0(s1)\n"
            "\tld   ra, 8(sp)\n"
            "\taddi sp, sp, 16\n"
            "\tret\n"
            "\n" + MUL32 + "\n"
        )

    return res.replace("\n\n\n", "\n\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data))
