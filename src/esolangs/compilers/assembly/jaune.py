import sys
from re import findall, sub


def count(code, ind):
    def check(k, s):
        ch = code[k]
        return ch.isnumeric() or ch in s

    start = code[ind]
    code += " "
    num = 0

    if start in "+-":
        if (n := code[ind - 1]).isnumeric():
            num = int(start + code[ind - 1])
            while check(ind, "+-"):
                x, y = code[ind : ind + 2]
                if x.isnumeric() and y in "+-":
                    num += int(y + x)
                ind += 1
        else:
            return n, ind + 1
    elif start in ":$@?!":
        if (c := code[ind - 1]) == "v":
            num = -1
        else:
            num = int(c)
        ind += 1
    else:
        while code[ind] == start:
            num += 1
            ind += 1

    return num, ind


def prep(code):
    def rep(sym):
        return sub(r"\d[?!]", "", sym)

    code = sub(r"[^^v><\d+\-#&:?!.$@;%]", "", code)
    code = sub("([#.;%])\1+", "\1", code)
    code = sub("v[:$]", "", code)

    jump: list = []
    rout: list = []

    for c in ":$":
        r = rf"(?:[\d]{c})+"
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
            if s[1] == "?":
                n = s.find("!")
            else:
                n = s.find("?")

            r += s[:2] + rep(s[2 : n - 1]) + s[n - 1 : n + 1] + rep(s[n + 1 :])
        else:
            r = s[:2] + rep(s[2:])

        code = code.replace(s, r)

    return code, jump, rout


def comp(code):
    def add(m):
        return m + 1 if m else ""

    code, jump, rout = prep(code)
    inp = [False, False]
    ind = 0

    res = (
        "global _start\n"
        "_start:\n"
        "\tlea ecx, [esp - 60]\n"
        "\txor edi, edi\n"
        "\tmov edx, 1\n"
        "\tmov esi, 1\n\n"
    )
    subr = {
        "^": ["output", False, False],
        "v": ["input", False, False],
        "<": ["left", False, False],
        "&": ["mult", False, False],
    }

    while ind < len(code):
        c = code[ind]
        num, new = count(code, ind)

        if c in "^v<":
            if num > 1:
                res += f"\tmov esi, {num}\n"
                subr[c][2] = True
            res += f"\tcall {subr[c][0]}\n"
            subr[c][1] = True
        elif c == "&":
            if num > 1:
                res += f"\tmov esi, {num}\n" f"\tcall {subr[c][0]}\n"
                subr[c][1] = subr[c][2] = True
            else:
                res += "\tadd [ecx], edi\n"
        elif c == ">":
            res += f"\tsub ecx, {4 * num}\n"
        elif c in "+-":
            if num:
                if isinstance(num, int):
                    if num > 1:
                        res += f"\tadd dword [ecx], {num}\n"
                    elif num == 1:
                        res += "\tinc dword [ecx]\n"
                    elif num == -1:
                        res += "\tdec dword [ecx]\n"
                    else:
                        res += f"\tsub dword [ecx], {-num}\n"
                else:
                    if c == "+":
                        res += "\tadd [ecx], eax\n"
                    else:
                        res += "\tsub [ecx], eax\n"
        elif c == "#":
            res += "\tmov edi, [ecx]\n"
        elif c == ":":
            res += f".label{add(num)}:\n"
        elif c in "?!":
            res += "\tcmp dword [ecx], 0\n" f'\tj{"n" if c == "?" else ""}e '
            if num >= 0:
                res += f".label{add(num)}\n"
            else:
                res += ".switch\n"
                inp[0] = True
        elif c == ".":
            res += "\n\tmov eax, 1\n" "\txor ebx, ebx\n" "\tint 80h\n"
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
            res += "\tmov dword [ecx], 0\n"

        ind = new

    if jump and inp[0]:
        res += "\n.switch:\n"
        for k in jump[:-1]:
            res += f"\tcmp eax, {k}\n" f"\tje .lab{add(k)}\n"
        for k in jump[::-1]:
            n = add(k)
            if k != jump[-1]:
                res += f".lab{n}:\n"
            res += f"\tjmp .label{n}\n"
    if rout and inp[1]:
        res += "\nswitch:\n"
        for k in rout[:-1]:
            res += f"\tcmp eax, {k}\n" f"\tje .sub{add(k)}\n"
        res += "\tret\n"
        for k in rout[::-1]:
            n = add(k)
            if k != rout[-1]:
                res += f".sub{n}:\n"
            res += f"\tcall sub{n}\n" "\tret\n"

    def end(opr):
        if subr[opr][2]:
            mul = (
                "\tdec esi\n"
                "\tcmp esi, 0\n"
                f"\tjg {subr[opr][0]}\n"
                "\tinc esi\n"
                "\tret\n"
            )
        else:
            mul = "\tret\n"
        return mul

    if subr["^"][1]:
        res += (
            "\noutput:\n"
            "\tmov edi, [ecx]\n"
            "\tpush edi\n"
            "\n\tmov eax, 10\n"
            "\tcmp edi, 0\n"
            "\tjge .max\n"
            "\n\tmov dword [ecx], '-'\n"
            "\tcall print\n"
            "\tneg edi\n"
            ".max:\n"
            "\tcmp eax, edi\n"
            "\tjg .main\n"
            "\tmov ebx, 10\n"
            "\tmul ebx\n"
            "\tjmp .max\n"
            ".main:\n"
            "\tmov ebx, 10\n"
            "\txor edx, edx\n"
            "\tdiv ebx\n"
            "\n\txchg eax, edi\n"
            "\txor edx, edx\n"
            "\tdiv edi\n"
            "\tmov [ecx], eax\n"
            "\tmov eax, edx\n"
            "\txchg eax, edi\n"
            "\n\tadd dword [ecx], '0'\n"
            "\tcall print\n"
            "\tsub dword [ecx], '0'\n"
            "\n\tcmp eax, 1\n"
            "\tje .done\n"
            "\tjmp .main\n"
            ".done:\n"
            "\tpop edi\n"
            "\tmov [ecx], edi\n" + end("^") + "\nprint:\n"
            "\tpush eax\n"
            "\tmov eax, 4\n"
            "\tmov ebx, 1\n"
            "\tmov edx, 1\n"
            "\tint 80h\n"
            "\tpop eax\n"
            "\tret\n"
        )
    if subr["v"][1]:
        s = (
            "\ninput:\n"
            "\tpush ecx\n"
            "\tmov eax, 3\n"
            "\tmov ebx, 0\n"
            "\tlea ecx, [esp - 4]\n"
            "\tint 80h\n"
            "\tmov eax, [esp - 4]\n"
            "\tsub eax, '0'\n" + end("v")
        )
        res += s.replace("ret", "pop ecx\n\tret")
    if subr["<"][1]:
        res += (
            "\nleft:\n"
            "\tlea ecx, [ecx + 4*esi]\n"
            "\tlea eax, [esp - 48]\n"
            "\tcmp eax, ecx\n"
            "\tjge .done\n"
            "\tmov ecx, eax\n"
            ".done:\n"
            "\tret\n"
        )
    if subr["&"][1]:
        res += (
            "\nmult:\n" "\tmov eax, edi\n" "\tmul esi\n" "\tadd [ecx], eax\n" "\tret\n"
        )

    return res.replace("\n\n\n", "\n\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data))
