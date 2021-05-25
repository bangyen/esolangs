import sys


def run(code):
    col = [1, 0, -1, 0]
    row = [0, 1, 0, -1]
    inp = []
    out = []

    rot = acc = 0
    x = y = 0

    if '.' in ''.join(code):
        for k in input('Input: '):
            inp += list('0' * 7 + bin(ord(k))[2:])[-7:]

    while x or y or not rot:
        try:
            ins = code[y][x]
        except IndexError:
            ins = ''

        if ins == 'R':
            rot = (rot + 1) % 4
        elif ins in '?!':
            if (ins == '?') == bool(acc):
                rot = (rot + 1) % 4
        elif ins == '+':
            acc += 1
        elif ins == '-':
            acc -= 1
        elif ins == '.':
            n = int(inp[0])
            acc = (acc | 1) - 1 + n
            inp = inp[1:] + [inp[0]]
        elif ins == ';':
            out.append(str(acc % 2))
        elif ins == 'S':
            acc = 0

        if len(out) == 7:
            print(chr(int(''.join(out), 2)), end='')
            out = []

        x += col[rot]
        y += row[rot]


if __name__ == '__main__':
    f = open(sys.argv[1])
    data = f.readlines()
    f.close()

    run(data)
