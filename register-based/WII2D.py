import secrets
import sys


def move(cur, arr, string):
    x = (cur[0] + arr[0]) % len(string)
    y = (cur[1] + arr[1]) % len(string[x])
    return x, y


def dist(x2, y2):
    def curry(v):
        x = abs(v[0] - x2)
        y = abs(v[1] - y2)
        return x + y
    return curry


def find(string, sym):
    lst = []
    for i in range(len(string)):
        for j in range(len(string[i])):
            if i and string[i][j] == sym:
                lst.append((i, j))
    return lst


def closest(cur, lst):
    lst.remove(cur)
    lst = sorted(lst, key=dist(*cur))
    return lst[0] if lst else None


dir_list = [
    vel := (-1, acc := 0),
    (1, 0), (0, -1), (0, 1)
]

op_list = [
    lambda x: x + 1,
    lambda x: x - 1,
    lambda x: x * 2,
    lambda x: x ** 2,
    lambda x: x // 2
]

if __name__ == '__main__':
    code = open(sys.argv[1]).readlines()
    start = find(code, '!')
    pos = start[0] if len(start) == 1 else None

    option = '^v<>?'
    direct = '^v<>'
    math = '+-*s/'

    while pos:
        op = code[pos[0]][pos[1]]
        if op in option:
            if op == '?':
                op = secrets.choice(direct)
            vel = dir_list[direct.index(op)]
        elif op == '|':
            a, b = vel
            vel = [-a, -b]
        elif op == '@':
            warps = closest(pos, find(code, '@'))
            if warps:
                pos = move(warps, [-1, 0], code)
                continue
        elif op.isdigit():
            acc = int(op)
        elif op in math:
            acc = op_list[math.index(op)](acc)
        elif op == '~':
            print(chr(acc), end='')
        elif op == '.':
            break
        pos = move(pos, vel, code)
