import sys
from typing import cast

from esolangs.interpreters.io import IO


def find(code: list[list[str | int | float]], ind: int) -> int:
    if "end" in (op := str(code[ind][0])):
        match = op[3:]
        move = -1
    else:
        match = "end" + op
        move = 1

    num = move
    ind += move

    while num:
        if ind == len(code):
            return ind
        if code[ind][0] == op:
            num += move
        elif code[ind][0] == match:
            num -= move
        ind += move
    return ind - 1


def run(lines: list[str], io: IO) -> None:
    ind = 0
    var: dict[str, int | float | str] = {}
    skip = False
    code: list[list[str | int | float]] = []

    for raw in lines:
        line = raw.lstrip().rstrip("\n").split(",")
        code.append([v.replace("*44", ",") for v in line if v])

    while ind < len(code):
        if (c := code[ind]) and not skip:
            for i, val in enumerate(c[1:]):
                if isinstance(val, str):
                    if val[0] == "$":
                        c[i + 1] = var[val[1:].strip()]
                    nxt = c[i + 1]
                    if isinstance(nxt, str) and nxt.isascii() and nxt.isdigit():
                        c[i + 1] = int(nxt)

            if (op := c[0]) == "print":
                io.print_line("".join(map(str, c[1:])))
            elif op == "input":
                var["answer"] = io.input_str(cast(str, c[1]))
            elif op == "make":
                if len(c) == 5:
                    if (o := c[3]) == "+":
                        v = cast(int | float, c[2]) + cast(int | float, c[4])
                    elif o == "-":
                        v = cast(int | float, c[2]) - cast(int | float, c[4])
                    elif o == "*":
                        v = cast(int | float, c[2]) * cast(int | float, c[4])
                    else:
                        v = cast(int | float, c[2]) / cast(int | float, c[4])
                    var[cast(str, c[1])] = v
                else:
                    var[cast(str, c[1])] = c[2]
            elif op == "if":
                lhs, cmp_op, rhs = c[1:4]
                if cmp_op == ">":
                    b = cast(int | float, lhs) > cast(int | float, rhs)
                elif cmp_op == "<":
                    b = cast(int | float, lhs) < cast(int | float, rhs)
                else:
                    b = lhs == rhs
                if not b:
                    ind = find(code, ind)
            elif op == "loop":
                if c[1]:
                    c[1] = cast(int | float, c[1]) - 1
                else:
                    ind = find(code, ind)
                    skip = True
            elif op == "endloop":
                ind = find(code, ind) + 1
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
