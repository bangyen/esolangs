import copy
import secrets
import sys


def init(lst):
    n = len(lst)
    m = len(lst[0])
    lst = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def move(x, y, vel):
        a, b = lst[vel]
        x = (x + a) % n
        y = (y + b) % m
        return x, y

    return move


def close(lst):
    def start(x, y):
        def dist(c):
            a = abs(c[0] - x)
            b = abs(c[1] - y)
            return a + b

        return dist

    pos = []

    for num, val in enumerate(lst):
        for n, v in enumerate(val):
            if num and v == "@":
                pos.append((num, n))

    def find(x, y):
        arr = copy.deepcopy(pos)
        arr.sort(key=start(x, y))
        if (c := (x, y)) in arr:
            arr.remove(c)
        return arr[0] if arr else None

    return find


def update(op, acc):
    if op.isdigit():
        return int(op)
    elif op == "+":
        return acc + 1
    elif op == "-":
        return acc - 1
    elif op == "*":
        return acc * 2
    elif op == "/":
        return acc // 2
    elif op == "s":
        return acc**2
    elif op == "~":
        print(chr(acc), end="")
    return acc


def run(code):
    for num, val in enumerate(code):
        if "!" in val:
            x, y = num, val.find("!")
            break
    else:
        return

    size = max(len(lst) for lst in code)
    code = [c.ljust(size) for c in code]

    find = close(code)
    move = init(code)
    vel = acc = 0

    while True:
        if (op := code[x][y]) in "^v<>":
            vel = "^v<>".index(op)
        elif op == "?":
            vel = secrets.randbelow(4)
        elif op == "|":
            if vel % 2:
                vel -= 1
            else:
                vel += 1
        elif op == "@":
            if w := find(x, y):
                x, y = w
                x -= 1
                continue
        elif op == ".":
            return

        acc = update(op, acc)
        x, y = move(x, y, vel)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
