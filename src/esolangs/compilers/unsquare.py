"""Compiler that turns Unsquare programs into RISC-V Linux assembly."""

from re import sub
from typing import Literal, get_args

from esolangs.compilers import _riscv_common as _common
from esolangs.compilers._riscv_common import Routine

# The seven commands that compile to a called subroutine rather than to
# inline instructions.
_Func = Literal["O", "I", "A", "S", "P", "o", "i"]
# Typed so the dispatch's membership test narrows the command to
# _Func, which is what keys the routine table below.
_SUBRS: frozenset[_Func] = frozenset(get_args(_Func))


def count(code: str, ind: int) -> tuple[int, int]:
    """Return the run length (or OI arithmetic value) at ``ind``."""
    code += "  "
    num = 0

    if (start := code[ind]) in "OI" and code[ind + 1] == "A":
        num = 0 if start == "O" else 1
        ind += 2

        while (ins := code[ind]) in "+-x":
            if ins == "+":
                num += 2
            elif ins == "-":
                num -= 2
            else:
                num *= 2
            ind += 1

        return num, ind
    if start in "+-":
        while (ins := code[ind]) in "+-":
            if ins == "+":
                num += 2
            else:
                num -= 2
            ind += 1
    else:
        while code[ind] == start:
            num += 1
            ind += 1

    return num, ind


def prep(code: str) -> str:
    """Filter to the command alphabet and simplify the OI arithmetic."""
    code = sub(r"[^OIAS+\-xPoi><]", "", code)
    ind = 0

    while ind + 1 < len(code):
        if code[ind] in "OI" and code[ind + 1] == "A":
            num, new = count(code, ind)
            if num in range(2) and new < len(code) and code[new] == ">":
                alt, res = new, 1
                while res and alt + 1 < len(code):
                    alt += 1
                    if (c := code[alt]) == ">":
                        res += 1
                    elif c == "<":
                        res -= 1
                if not res:
                    code = code.replace(code[ind : alt + 1], code[ind:new])
        ind += 1

    code = sub(r"([OI]A[+\-x]*)+", r"\1", code)
    code = sub("(OO|II|PP)S+", r"\1", code)

    return code.replace("SS", "")


def comp(code: str) -> str:
    """Compile an Unsquare program to RISC-V assembly with a data stack."""
    res = (
        "    .text\n"
        "    .global _start\n"
        "_start:\n"
        "    addi s1, sp, -4\n"
        "    li   s2, 0\n"
        "    li   s3, 1\n\n"
    )
    func: dict[_Func, Routine] = {
        "O": Routine("zero"),
        "I": Routine("one"),
        "A": Routine("down"),
        "S": Routine("swap"),
        "P": Routine("up"),
        "o": Routine("output"),
        "i": Routine("input"),
    }

    code = prep(code)
    ind = jmp = 0

    while ind < len(code):
        num, new = count(code, ind)
        if (c := code[ind]) in "OI" and (code + " ")[ind + 1] == "A":
            res += f"\tli   s2, {num}\n"
            ind = new
            continue
        if c in _SUBRS:
            routine = func[c]
            if num > 1:
                res += f"\tli   s3, {num}\n"
                routine.looped = True
            res += f"\tcall {routine.label}\n"
            routine.used = True
        elif c in "+-":
            if num:
                res += f"\taddi s2, s2, {num}\n"
        elif c == "x":
            res += f"\tslli s2, s2, {num}\n"
        elif c == ">":
            jmp += 1
            res += f".T{jmp}:\n\tli   t0, 2\n\tbltu s2, t0, .B{jmp}\n"
        else:
            # ``prep`` keeps only ``OIASP+-xoi><`` and every other character
            # of it has an arm above, so what is left here is ``<``.
            res += f"\tj .T{jmp}\n.B{jmp}:\n"
            jmp -= 1

        ind = new

    res += "\n\tli   a0, 0\n\tli   a7, 93\n\tecall\n\n"

    def end(opr: _Func) -> str:
        if func[opr].looped:
            mul = (
                "\taddi s3, s3, -1\n"
                f"\tbgt  s3, zero, {func[opr].label}\n"
                "\taddi s3, s3, 1\n"
                "\tret\n"
            )
        else:
            mul = "\tret\n"
        return mul

    if func["O"].used:
        res += "zero:\n\taddi s1, s1, -4\n\tsw   zero, 0(s1)\n" + end("O")
    if func["I"].used:
        res += "one:\n\taddi s1, s1, -4\n\tli   t0, 1\n\tsw   t0, 0(s1)\n" + end("I")
    if func["P"].used:
        res += "up:\n\taddi s1, s1, -4\n\tsw   s2, 0(s1)\n" + end("P")
    if func["A"].used:
        if func["A"].looped:
            res += (
                "down:\n"
                "\taddi s3, s3, -1\n"
                "\tslli t0, s3, 2\n"
                "\tadd  s1, s1, t0\n"
                "\tlw   s2, 0(s1)\n"
                "\taddi s1, s1, 4\n"
                "\tli   s3, 1\n"
                "\tret\n"
            )
        else:
            res += "down:\n\tlw   s2, 0(s1)\n\taddi s1, s1, 4\n\tret\n"
    if func["S"].used:
        res += (
            "swap:\n"
            "\tlw   t0, 0(s1)\n"
            "\tlw   t1, 4(s1)\n"
            "\tsw   t1, 0(s1)\n"
            "\tsw   t0, 4(s1)\n"
            "\tret\n"
        )
    if func["o"].used:
        res += (
            "output:\n"
            "\tli   a7, 64\n"
            "\tli   a0, 1\n"
            "\tmv   a1, s1\n"
            "\tli   a2, 1\n"
            "\tecall\n" + end("o")
        )
    if func["i"].used:
        res += (
            "input:\n"
            "\taddi s1, s1, -4\n"
            "\tli   a7, 63\n"
            "\tli   a0, 0\n"
            "\tmv   a1, s1\n"
            "\tli   a2, 1\n"
            "\tecall\n" + end("i")
        )

    return res.replace(":\n\n", ":\n").strip() + "\n"


if __name__ == "__main__":  # pragma: no cover
    _common.main(comp)
