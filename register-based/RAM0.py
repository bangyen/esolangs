import re
import sys


def init():
    z = n = 0
    ram: dict = {}

    def output():
        res = f"z: {z}\n" f"n: {n}\n" "ram: {"

        for x, y in ram.items():
            res += f"\n    {x}: {y},"
        if ram:
            res = res[:-1] + "\n"
        print(res + "}")

    def change(op):
        nonlocal z, n
        if op == "Z":
            z = 0
        elif op == "A":
            z += 1
        elif op == "N":
            n = z
        elif op == "L":
            z = ram.get(z, 0)
        elif op == "S":
            ram[n] = z
        elif op == 0:
            output()
        return not z

    return change


def run(code):
    expr = r"([ZANCLS]|[1-9]\d*)"
    code = re.findall(expr, code)
    func = init()
    ind = 0

    while ind < len(code):
        skip = func(c := code[ind])
        if c == "C" and skip:
            ind += 1
        elif c.isdigit():
            ind = int(c) - 2
        ind += 1

    func(0)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
