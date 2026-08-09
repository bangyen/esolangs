import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    stk: list[int] = []
    lst: list[int] = []
    ind = 0

    while ind < len(code):
        if (char := code[ind]) == ">":
            stk.append(0)
        elif char == "<":
            if not stk:
                raise HaltError
            stk.pop()
        elif char == "+":
            if not stk:
                raise HaltError
            stk[-1] = (stk[-1] + 1) % 256
        elif char == "-":
            if not stk:
                raise HaltError
            stk[-1] = (stk[-1] - 1) % 256
        elif char == ".":
            if not stk:
                raise HaltError
            io.print_char(chr(stk[-1]))
        elif char == ",":
            stk.append(io.input_char())
        elif char == "[":
            if not stk:
                raise HaltError
            if stk[-1]:
                lst.append(ind)
            else:
                match = 1
                while match:
                    ind += 1
                    if ind == len(code):
                        break
                    if (o := code[ind]) == "[":
                        match += 1
                    elif o == "]":
                        match -= 1
        elif char == "]":
            if not lst:
                raise HaltError
            ind = lst.pop() - 1

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
