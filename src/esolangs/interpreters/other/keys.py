import re
import sys

from esolangs.interpreters.io import IO


def run(code: list[str], io: IO) -> None:
    x = code[0].strip()
    y = code[1].strip()
    r = re.compile(r"(-_|_-|\\-|/" r"_|[^\\/\-_])")

    if x == y and not r.search(x):
        io.print_line("Accept.")
    else:
        io.print_line("Reject.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
