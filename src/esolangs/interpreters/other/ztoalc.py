import sys
from dataclasses import dataclass


@dataclass
class State:
    inp: bool = False


def run(code):
    ptr = int(code[0])
    state = State()
    var: dict = {}

    def val(state, exp):
        if exp == "input":
            s = ord(input("\n" * state.inp + "Input: ")[0])
            state.inp = False
            return s
        elif exp in var:
            return var.get(exp)
        elif exp.isnumeric() or exp[0] == "-" and exp[1:].isnumeric():
            return int(exp)
        elif exp[0] == "[":
            return [0] * val(state, exp[1:-1])
        else:
            arg = exp[:-1].split("[")
            return var[arg[0]][val(state, arg[1])]

    while p := ptr - 1:
        ins = code[p] if p < len(code) else ""
        lst = ins.split()

        if "print" in ins:
            print(chr(val(state, lst[1])), end="")
            state.inp = True
        elif "jump" in ins:
            if val(state, lst[2]):
                ptr += 1
                continue
        elif " =" in ins:
            var[lst[0]] = val(state, lst[2])
        elif "+" in ins:
            var[lst[0]] += val(state, lst[2])
        elif "-" in ins:
            var[lst[0]] -= val(state, lst[2])

        if ptr % 2:
            ptr = 3 * ptr + 1
        else:
            ptr //= 2


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
