import secrets
import sys
from dataclasses import dataclass, field


@dataclass
class State:
    stk: list = field(default_factory=list)
    num: bool = True
    new: bool = False
    ptr: int = 0
    comm: int = 0


def run(code):
    code = code.split()
    state = State()

    def parse(state, char):
        rest = code[state.ptr][1:]

        if char == "@":
            s = input("\n" * state.new + "Input: ")
            state.stk.extend(ord(c) for c in s)
            state.new = False
        elif char == "v":
            state.stk.append(int(rest))
        elif char == "*":
            state.stk.extend(ord(c) for c in rest)
        elif char in "oO":
            state.num = char == "O"
        elif char == "+":
            state.stk.append(state.stk[-1])
        elif char == ":":
            state.ptr += 1
            n = len(state.stk)
            while len(state.stk) == n:
                parse(state, code[state.ptr][0])
        elif char == "\\":
            state.ptr += 1
            while len(state.stk):
                parse(state, code[state.ptr][0])
        elif char == "€":
            parse(state, secrets.choice("@v*oO+:\\"))

        while state.stk and sum(state.stk[1:]) / 2 > state.stk[0]:
            state.new = True
            n = state.stk.pop(0) - 1
            print(n if state.num else chr(n), end="")

        state.comm += 1
        if state.comm % 15 == 0:
            state.stk = []

    while state.ptr < len(code):
        parse(state, code[state.ptr][0])
        state.ptr += 1


if __name__ == "__main__":
    f = open(sys.argv[1], encoding="utf-8")
    data = f.read()
    f.close()

    run(data)
