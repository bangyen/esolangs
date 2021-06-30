import sys
import re


def run(code):
    ptr = 0
    stk = [[], []]
    app = stk[ptr].append
    pop = stk[ptr].pop

    dct = {
        '`': lambda: app(1 - ptr),
        '^': lambda: app(stk[ptr][-1]),
        '0': lambda: app(0),
        '+': lambda: app(pop() + 1),
        '-': lambda: app(pop() - 1),
        '.': lambda: print(pop(), end=''),
        '=': lambda: stk[1 - ptr].append(pop()),
        ';': lambda: pop()
    }

    def ins(sym):
        nonlocal ptr
        ind = 0

        while ind < len(sym):
            if (char := sym[ind]) in dct:
                dct[char]()
            elif char == '~':
                ptr ^= 1
            elif char == '*':
                stk[ptr] = stk[ptr][::-1]
            elif char == '?':
                if not pop():
                    ind += 1
            elif char == '!':
                ins(pop())
            elif char in '"\'':
                s = (re.match('[^"]*', sym[ind + 1:])
                     [0].replace('`', '"'))
                ind += len(s) + 1
                if char == '\'':
                    s = f'"{s}"'

                app(s)

            ind += 1

    ins(code)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
