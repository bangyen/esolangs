import sys


def init(code):
    col = [1, 0, -1, 0]
    row = [0, 1, 0, -1]
    x = y = r = 0

    def move(acc):
        nonlocal x, y, r
        o = code[y][x]
        c = (o == "R") or (o == "?" and acc) or (o == "!" and not acc)

        r = (r + c) % 4
        x += col[r]
        y += row[r]
        b = x or y or not r

        return o, b

    return move


def run(code):
    size = max(len(lne) for lne in code)
    code = [c.ljust(size) for c in code]
    move = init(code)
    cont = True

    inp = []
    out = []
    acc = 0

    if "." in "".join(code):
        for k in input("Input: "):
            val = bin(ord(k))[2:]
            inp += list(val.zfill(7))

    while cont:
        ins, cont = move(acc)
        if ins in "R?!":
            continue
        elif ins == "+":
            acc += 1
        elif ins == "-":
            acc -= 1
        elif ins == ".":
            n = int(inp[0])
            acc = (acc | 1) - 1 + n
            inp = inp[1:] + [inp[0]]
        elif ins == ";":
            out.append(str(acc % 2))
        elif ins == "S":
            acc = 0

        if len(out) == 7:
            char_val: int = int("".join(out), 2)
            print(chr(char_val), end="")
            out = []


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
