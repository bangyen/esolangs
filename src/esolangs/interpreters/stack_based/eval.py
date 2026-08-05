import re
import sys


def run(code):
    ptr = 0
    stk: list = [[], []]

    dct = {
        "`": lambda: stk[ptr].append(1 - ptr),
        "^": lambda: stk[ptr].append(stk[ptr][-1]),
        "0": lambda: stk[ptr].append(0),
        "+": lambda: stk[ptr].append(stk[ptr].pop() + 1),
        "-": lambda: stk[ptr].append(stk[ptr].pop() - 1),
        ".": lambda: print(stk[ptr].pop(), end=""),
        "=": lambda: stk[1 - ptr].append(stk[ptr].pop()),
        ";": lambda: stk[ptr].pop(),
    }

    def ins(sym):
        nonlocal ptr
        ind = 0

        while ind < len(sym):
            if (char := sym[ind]) in dct:
                dct[char]()
            elif char == "~":
                ptr ^= 1
            elif char == "*":
                stk[ptr] = stk[ptr][::-1]
            elif char == "?":
                if not stk[ptr].pop():
                    ind += 1
            elif char == "!":
                ins(stk[ptr].pop())
            elif char in "\"'":
                match = re.match('[^"]*', sym[ind + 1 :])
                s = match[0].replace("`", '"') if match else ""
                ind += len(s) + 1
                if char == "'":
                    s = f'"{s}"'

                stk[ptr].append(s)

            ind += 1

    ins(code)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
