import re
import sys


def run(code):
    lst = ("INJECT", "PUSH", "EJECT", "POP", "INVERT", r"GOTO *(\d+)")

    join = f'({"|".join(lst)})'
    code = re.findall(join, code)
    ind = reg = 0
    deq = []

    while ind < len(code):
        sym = code[ind][0]
        if sym == "PUSH":
            deq.append(reg)
        elif sym == "INJECT":
            deq.insert(0, reg)
        elif sym == "POP":
            reg = deq.pop() if deq else 0
        elif sym == "EJECT":
            reg = deq.pop(0) if deq else 0
        elif sym == "INVERT":
            reg ^= 1
        elif reg:
            num = int(sym[4:])
            ind = num - 1

        ind += 1
    print(*deq)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
