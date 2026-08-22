"""Compiler that turns Unsquare programs into RISC-V Linux assembly."""

import sys
from re import sub


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
    code = sub("(OO|II|PP)S+", "\1", code)

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
    func = {
        "O": ["zero", False, False],
        "I": ["one", False, False],
        "A": ["down", False, False],
        "S": ["swap", False, False],
        "P": ["up", False, False],
        "o": ["output", False, False],
        "i": ["input", False, False],
    }

    code = prep(code)
    ind = jmp = 0

    while ind < len(code):
        num, new = count(code, ind)
        if (c := code[ind]) in "OI" and (code + " ")[ind + 1] == "A":
            res += f"\tli   s2, {num}\n"
            ind = new
            continue
        if c in "OIASPoi":
            if num > 1:
                res += f"\tli   s3, {num}\n"
                func[c][2] = True
            res += f"\tcall {func[c][0]}\n"
            func[c][1] = True
        elif c in "+-":
            if num:
                res += f"\taddi s2, s2, {num}\n"
        elif c == "x":
            res += f"\tslli s2, s2, {num}\n"
        elif c == ">":
            jmp += 1
            res += f".T{jmp}:\n\tli   t0, 2\n\tbltu s2, t0, .B{jmp}\n"
        elif c == "<":
            res += f"\tj .T{jmp}\n.B{jmp}:\n"
            jmp -= 1

        ind = new

    res += "\n\tli   a0, 0\n\tli   a7, 93\n\tecall\n\n"

    def end(opr: str) -> str:
        if func[opr][2]:
            mul = (
                "\taddi s3, s3, -1\n"
                f"\tbgt  s3, zero, {func[opr][0]}\n"
                "\taddi s3, s3, 1\n"
                "\tret\n"
            )
        else:
            mul = "\tret\n"
        return mul

    if func["O"][1]:
        res += "zero:\n\taddi s1, s1, -4\n\tsw   zero, 0(s1)\n" + end("O")
    if func["I"][1]:
        res += "one:\n\taddi s1, s1, -4\n\tli   t0, 1\n\tsw   t0, 0(s1)\n" + end("I")
    if func["P"][1]:
        res += "up:\n\taddi s1, s1, -4\n\tsw   s2, 0(s1)\n" + end("P")
    if func["A"][1]:
        if func["A"][2]:
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
    if func["S"][1]:
        res += (
            "swap:\n"
            "\tlw   t0, 0(s1)\n"
            "\tlw   t1, 4(s1)\n"
            "\tsw   t1, 0(s1)\n"
            "\tsw   t0, 4(s1)\n"
            "\tret\n"
        )
    if func["o"][1]:
        res += (
            "output:\n"
            "\tli   a7, 64\n"
            "\tli   a0, 1\n"
            "\tmv   a1, s1\n"
            "\tli   a2, 1\n"
            "\tecall\n" + end("o")
        )
    if func["i"][1]:
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


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data))
