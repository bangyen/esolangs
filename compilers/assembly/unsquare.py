import sys
from re import sub


def count(code, ind):
    code += "  "
    num = 0

    if (start := code[ind]) in "OI":
        if code[ind + 1] == "A":
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


def prep(code):
    code = sub(r"[^OIAS+\-xPoi><]", "", code)
    ind = 0

    while ind + 1 < len(code):
        if code[ind] in "OI" and code[ind + 1] == "A":
            num, new = count(code, ind)
            if num in range(2) and new < len(code) and code[new] == ">":
                alt, res = new, 1
                while res:
                    alt += 1
                    if (c := code[alt]) == ">":
                        res += 1
                    elif c == "<":
                        res -= 1
                code = code.replace(code[ind : alt + 1], code[ind:new])
        ind += 1

    code = sub(r"([OI]A[+\-x]*)+", r"\1", code)
    code = sub("(OO|II|PP)S+", "\1", code)

    return code.replace("SS", "")


def comp(code):
    res = (
        "global _start\n"
        "_start:\n"
        "\tlea ecx, [esp - 4]\n"
        "\txor edi, edi\n"
        "\tmov edx, 1\n"
        "\tmov esi, 1\n\n"
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
        if (c := code[ind]) in "OI":
            if (code + " ")[ind + 1] == "A":
                res += f"\tmov edi, {num}\n"
                ind = new
                continue
        if c in "OIASPoi":
            if num > 1:
                res += f"\tmov esi, {num}\n"
                func[c][2] = True
            res += f"\tcall {func[c][0]}\n"
            func[c][1] = True
        elif c in "+-":
            if num:
                if num > 0:
                    res += f"\tadd edi, {num}\n"
                else:
                    res += f"\tsub edi, {-num}\n"
        elif c == "x":
            res += f"\tshl edi, {num}\n"
        elif c == ">":
            jmp += 1
            res += f".T{jmp}:\n" "\tcmp edi, 2\n" f"\tjb .B{jmp}\n"
        elif c == "<":
            res += f"\tjmp .T{jmp}\n" f".B{jmp}:\n"
            jmp -= 1

        ind = new

    res += "\n\tmov eax, 1\n" "\txor ebx, ebx\n" "\tint 80h\n\n"

    def end(opr):
        if func[opr][2]:
            mul = (
                "\tdec esi\n"
                "\tcmp esi, 0\n"
                f"\tjg {func[opr][0]}\n"
                "\tinc esi\n"
                "\tret\n"
            )
        else:
            mul = "\tret\n"
        return mul

    if func["O"][1]:
        res += "zero:\n" "\tsub ecx, 4\n" "\tmov dword [ecx], 0\n" + end("O")
    if func["I"][1]:
        res += "one:\n" "\tsub ecx, 4\n" "\tmov dword [ecx], 1\n" + end("I")
    if func["P"][1]:
        res += "up:\n" "\tsub ecx, 4\n" "\tmov dword [ecx], edi\n" + end("P")
    if func["A"][1]:
        if func["A"][2]:
            res += (
                "down:\n"
                "\tdec esi\n"
                "\tlea ecx, [ecx + 4*esi]\n"
                "\tmov edi, [ecx]\n"
                "\tadd ecx, 4\n"
                "\tmov esi, 1\n"
                "\tret\n"
            )
        else:
            res += "down:\n" "\tmov edi, [ecx]\n" "\tadd ecx, 4\n" "\tret\n"
    if func["S"][1]:
        res += (
            "swap:\n"
            "\tmov eax, [ecx]\n"
            "\tmov ebx, [ecx + 4]\n"
            "\tmov [ecx], ebx\n"
            "\tmov [ecx + 4], eax\n"
            "\tret\n"
        )
    if func["o"][1]:
        res += "output:\n" "\tmov eax, 4\n" "\tmov ebx, 1\n" "\tint 80h\n" + end("o")
    if func["i"][1]:
        res += (
            "input:\n"
            "\tsub ecx, 4\n"
            "\tmov eax, 3\n"
            "\txor ebx, ebx\n"
            "\tint 80h\n" + end("i")
        )

    return res.replace(":\n\n", ":\n").strip() + "\n"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data))
