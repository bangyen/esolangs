import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    stk: list[int] = []
    lst: list[int] = []
    ind = 0

    while ind < len(code):
        if (char := code[ind]) == ">":
            stk.append(0)
        elif char == "<":
            stk.pop()
        elif char == "+":
            stk[-1] = (stk[-1] + 1) % 256
        elif char == "-":
            stk[-1] = (stk[-1] - 1) % 256
        elif char == ".":
            io.print_char(chr(stk[-1]))
        elif char == ",":
            stk.append(io.input_char())
        elif char == "[":
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
            ind = lst.pop() - 1

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
