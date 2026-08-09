import re
import sys

from esolangs.interpreters.io import IO


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
    """Map each bracket to its partner, ``{open: close, close: open}``.

    Raises :class:`ValueError` if the brackets are unbalanced: the spec
    defines ``[``/``]`` only for matched pairs.
    """
    stack: list[int] = []
    res: dict[int, int] = {}
    for i, char in enumerate(code):
        if char == "[":
            stack.append(i)
        elif char == "]":
            if not stack:
                raise ValueError(f"unmatched ']' at position {i}")
            open_i = stack.pop()
            res[open_i] = i
            res[i] = open_i
    if stack:
        raise ValueError(f"unmatched '[' at position {stack[-1]}")
    return res


def run(code: str, io: IO) -> None:
    tape: list[int] = [0]
    code = parse(code)
    m = matches(code)

    ind = ptr = 0

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
            io.print_char(chr(tape[ptr]))
        elif char == ",":
            tape[ptr] = io.input_char()
        elif (char == "[" and tape[ptr] == 0) or (char == "]" and tape[ptr] != 0):
            ind = m[ind]

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
