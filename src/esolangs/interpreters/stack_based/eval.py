import re
import sys
from dataclasses import dataclass, field


@dataclass
class State:
    ptr: int = 0
    stk: list = field(default_factory=lambda: [[], []])


def run(code):
    state = State()

    dct = {
        "`": lambda: state.stk[state.ptr].append(1 - state.ptr),
        "^": lambda: state.stk[state.ptr].append(state.stk[state.ptr][-1]),
        "0": lambda: state.stk[state.ptr].append(0),
        "+": lambda: state.stk[state.ptr].append(state.stk[state.ptr].pop() + 1),
        "-": lambda: state.stk[state.ptr].append(state.stk[state.ptr].pop() - 1),
        ".": lambda: print(state.stk[state.ptr].pop(), end=""),
        "=": lambda: state.stk[1 - state.ptr].append(state.stk[state.ptr].pop()),
        ";": lambda: state.stk[state.ptr].pop(),
    }

    def ins(sym):
        ind = 0

        while ind < len(sym):
            if (char := sym[ind]) in dct:
                dct[char]()
            elif char == "~":
                state.ptr ^= 1
            elif char == "*":
                state.stk[state.ptr] = state.stk[state.ptr][::-1]
            elif char == "?":
                if not state.stk[state.ptr].pop():
                    ind += 1
            elif char == "!":
                ins(state.stk[state.ptr].pop())
            elif char in "\"'":
                match = re.match('[^"]*', sym[ind + 1 :])
                s = match[0].replace("`", '"') if match else ""
                ind += len(s) + 1
                if char == "'":
                    s = f'"{s}"'

                state.stk[state.ptr].append(s)

            ind += 1

    ins(code)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
