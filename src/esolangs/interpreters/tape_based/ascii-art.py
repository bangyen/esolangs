import re
import sys


def parse(code: str) -> str:
    if not code:
        return ""
    code = re.sub(" +\n", "\n", code)
    blocks = code.split("\n\n")
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

    for c in blocks:
        t = (c.count("\n"), c[-1])
        if t in sym:
            res += sym[t]
    return res


def matches(code: str) -> dict[int, int]:
    """Map each bracket to its partner, ``{open: close, close: open}``."""
    stack: list[int] = []
    res: dict[int, int] = {}
    for i, char in enumerate(code):
        if char == "[":
            stack.append(i)
        elif char == "]" and stack:
            open_i = stack.pop()
            res[open_i] = i
            res[i] = open_i
    return res


def run(code: str) -> None:
    tape: list[int] = [0]
    code = parse(code)
    m = matches(code)

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
            val = input("\nInput: "[new:])
            tape[ptr] = ord(val[0])
            new = 1
        elif char == "[" and tape[ptr] == 0:
            partner = m.get(ind)
            if partner is None:
                return  # unmatched "[": halt
            ind = partner
        elif char == "]" and tape[ptr] != 0:
            partner = m.get(ind)
            if partner is None:
                return  # unmatched "]": halt
            ind = partner

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
