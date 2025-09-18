import sys


def run(code):
    size = max(len(lne) for lne in code)
    code = [c.ljust(size) for c in code]

    x, y = 0, 0
    a, b = 0, 1
    tape = [0]
    cell = 0

    while True:
        if (c := code[x][y]) == "\\":
            a, b = b, a
        elif c == "/":
            a, b = -b, -a
        elif c == "<":
            if cell:
                cell -= 1
        elif c == ">":
            cell += 1
            if cell == len(tape):
                tape.append(0)
        elif c == "-":
            tape[cell] ^= 1
        elif c == "+" and not tape[cell]:
            x, y = x + a, y + b
        elif c == "*":
            break

        x = (x + a) % len(code)
        y = (y + b) % size

    print(*tape)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
