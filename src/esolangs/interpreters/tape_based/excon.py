import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    pool: list[int] = [0] * 8
    cell = 7

    for sym in code:
        if sym == ":":
            pool, cell = ([0] * 8, 7)
        elif sym == "^":
            pool[cell] ^= 1
        elif sym == "!":
            num = "".join(map(str, pool))
            io.print_char(chr(int(num, 2)))
        elif sym == "<":
            cell -= 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
