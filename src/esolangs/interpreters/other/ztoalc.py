import sys
from dataclasses import dataclass
from typing import cast

from esolangs.interpreters.io import IO


@dataclass
class State:
    pass


def run(code: list[str], io: IO) -> None:
    ptr = int(code[0])
    state = State()
    var: dict[str, int | list[int]] = {}

    def val(state: State, exp: str) -> int | list[int]:
        if exp == "input":
            return io.input_char()
        if exp in var:
            return var[exp]
        if exp.isnumeric() or (exp[0] == "-" and exp[1:].isnumeric()):
            return int(exp)
        if exp[0] == "[":
            return [0] * cast(int, val(state, exp[1:-1]))
        arg = exp[:-1].split("[")
        arr = var[arg[0]]
        if not isinstance(arr, list):
            raise ValueError("array variable expected")  # pragma: no cover
        return arr[cast(int, val(state, arg[1]))]

    while p := ptr - 1:
        ins = code[p] if p < len(code) else ""
        lst = ins.split()

        if "print" in ins:
            io.print_char(chr(cast(int, val(state, lst[1]))))
        elif "jump" in ins:
            if val(state, lst[2]):
                ptr += 1
                continue
        elif " =" in ins:
            var[lst[0]] = val(state, lst[2])
        elif "+" in ins:
            var[lst[0]] = cast(int, var[lst[0]]) + cast(int, val(state, lst[2]))
        elif "-" in ins:
            var[lst[0]] = cast(int, var[lst[0]]) - cast(int, val(state, lst[2]))

        if ptr % 2:
            ptr = 3 * ptr + 1
        else:
            ptr //= 2


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
