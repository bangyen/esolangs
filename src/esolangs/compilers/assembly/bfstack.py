import itertools
import re
import sys


def parse(code: str) -> list[tuple[str, int]]:
    def con(*s: str) -> tuple[str, int]:
        if s[0] in "+-":
            x = s.count("+")
            y = s.count("-")
            return "+", x - y
        return s[0], len(s)

    def key(v: str) -> str:
        if v in "+-":
            return "+"
        return v

    filtered = re.sub(r"[^><+-.,\][]", "", code)

    while re.search(r"(>[+-]*<|\+-|-\+)", filtered):
        filtered = re.sub(">[+-]*<", "", filtered)
        filtered = filtered.replace("+-", "").replace("-+", "")

    while m := re.search(r"[>\]]\[", filtered):
        ind = m.start() + 1
        mat = 1

        while mat:
            ind += 1
            if ind == len(filtered):
                return []
            elif (c := filtered[ind]) == "[":
                mat += 1
            elif c == "]":
                mat -= 1

        filtered = filtered[: m.start() + 1] + filtered[ind + 1 :]

    filtered = re.sub(r"[+-]*\[[+-]]", "0", filtered)
    filtered = re.sub("[+-]+<", "<", filtered)
    grouped = itertools.groupby(filtered, key=key)
    return [con(*g) for _, g in grouped]


def comp(code: str) -> str:
    tokens = parse(code)
    jump = 0
    arr = []
    res = (
        "global _start\n"
        "_start:\n"
        "\tlea ecx, [esp - 6]\n"
        "\tmov edx, 1\n"
        "\tmov esi, 1\n\n"
    )

    ins = {
        ">": ["right", False, False],
        "<": ["left", False, False],
        ".": ["output", False, False],
        ",": ["input", False, False],
    }

    for char, num in tokens:
        if char == "+":
            if num > 1:
                res += f"\tadd byte [ecx], {num}\n"
            elif num == 1:
                res += "\tinc byte [ecx]\n"
            elif num == -1:
                res += "\tdec byte [ecx]\n"
            elif num < -1:
                res += f"\tsub byte [ecx], {-num}\n"
        elif char == "0":
            res += "\tmov byte [ecx], 0\n"
        elif char in "><.,":
            if num > 1:
                res += f"\tmov esi, {num}\n"
                ins[char][2] = True
            res += f"\tcall {ins[char][0]}\n"

            ins[char][1] = True
        elif char in "[]":
            for _ in range(num):
                if char == "[":
                    jump += 1
                    arr.append(jump)
                    res += f".T{jump}:\n" "\tcmp byte [ecx], 0\n" f"\tje .B{jump}\n"
                elif arr:
                    m = arr.pop()
                    res += f"\tjmp .T{m}\n" f".B{m}:\n"

    res += "\n\tmov eax, 1\n" "\txor ebx, ebx\n" "\tint 80h\n"

    def end(s, mul):
        return (
            mul * ("\tdec esi\n" "\tcmp esi, 0\n" f"\tjg {s}\n" "\tinc esi\n")
            + "\tret\n"
        )

    if ins[">"][1]:
        res += (
            "\nright:\n"
            "\tdec ecx\n"
            "\tmov byte [ecx], 0\n" + end("right", ins[">"][2])
        )
    if ins["<"][1]:
        res += (
            "\nleft:\n"
            "\tlea edi, [esp - 1]\n"
            "\tcmp ecx, edi\n"
            "\tje .done\n"
            "\tinc ecx\n"
        )
        if ins["<"][2]:
            res += "\tdec esi\n" "\tcmp esi, 0\n" "\tjg left\n" "\tinc esi\n"
        res += ".done:\n" "\tret\n"
    if ins["."][1]:
        res += (
            "\noutput:\n"
            "\tmov eax, 4\n"
            "\tmov ebx, 1\n"
            "\tint 80h\n" + end("output", ins["."][2])
        )
    if ins[","][1]:
        res += (
            "\ninput:\n"
            "\tmov eax, 3\n"
            "\txor ebx, ebx\n"
            "\tdec ecx\n"
            "\tint 80h\n" + end("input", ins[","][2])
        )

    return res


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = f.read()

        with open("output.asm", "w") as f:
            f.write(comp(data))
