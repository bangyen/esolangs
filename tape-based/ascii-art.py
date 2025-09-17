import re
import sys


def parse(code):
    code = re.sub(" +\n", "\n", code)
    code = code.split("\n\n")
    res = ""
    sym = {
        (0, "-"): "-",
        (1, "#"): ".",
        (2, "|"): ",",
        (3, "\\"): "<",
        (3, "/"): ">",
        (4, "|"): "+",
        (5, "_"): "[",
        (5, "|"): "]",
    }

    for c in code:
        t = (c.count("\n"), c[-1])
        if t in sym:
            res += sym[t]
    return res


def init(code, tape):
    stk = []

    def find(ind, ptr):
        if code[ind] == "[":
            if tape[ptr]:
                stk.append(ind)
            else:
                match = 1
                while match:
                    ind += 1
                    if ind == len(code):
                        return
                    elif code[ind] == "[":
                        match += 1
                    elif code[ind] == "]":
                        match -= 1
        else:
            if tape[ptr]:
                return stk[-1]
            stk.pop()
        return ind

    return find


def run(code):
    tape = [0]
    code = parse(code)
    find = init(code, tape)

    ind = ptr = 0
    new = 1

    while ind < len(code):
        char = code[ind]
        if char == ">":
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif char == "<" and ptr:
            ptr -= 1
        elif char in "+":
            tape[ptr] = (tape[ptr] + 1) % 256
        elif char == "-":
            tape[ptr] = (tape[ptr] - 1) % 256
        elif char == ".":
            print(chr(tape[ptr]), end="")
            new = 0
        elif char == ",":
            val = input("\nInput: "[:new])
            tape[ptr] = ord(val[0])
            new = 1
        elif char in "[]":
            new_ind = find(ind, ptr)
            if new_ind is None:
                return
            ind = new_ind
            continue  # Skip the increment since ind was updated by find()

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
