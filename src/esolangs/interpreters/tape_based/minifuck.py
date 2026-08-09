import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    tape: list[int] = [0] * 8
    ptr = ind = 0

    while ind < len(code):
        ins = code[ind]
        if ins == "<" and ptr:
            ptr -= 1
        elif ins in ".[":
            ptr += 1
            if ptr + 1 >= len(tape):
                tape.append(0)
            tape[ptr] ^= 1

            if ins == ".":
                lst = map(str, tape[:8])
                if n := int("".join(lst), 2):
                    io.print_char(chr(n))
                else:
                    val = bin(io.input_char())[2:].zfill(8)
                    tape = [*map(int, val), *tape[8:]]
            elif not tape[ptr]:
                tape[ptr + 1] ^= 1
                ind += 1

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
