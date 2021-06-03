import sys


def find(code, ind, op):
    if 'end' in op:
        match = op[3:]
        move = -1
    else:
        match = 'end' + op
        move = 1

    num = move
    ind += move

    while num:
        if code[ind][0] == op:
            num += move
        elif code[ind][0] == match:
            num -= move
        ind += move

    return ind - 1


def run(code):
    ind = 0
    var = {}
    code = [
        k.lstrip()
        .rstrip('\n')
        .split(',')
        for k in code
    ]

    for y in code:
        for a, b in enumerate(y):
            y[a] = b.replace('*44', ',')

    while ind < len(code):
        if c := code[ind]:
            for x, y in enumerate(c):
                if isinstance(y, str) and y[0] == '$':
                    c[x] = var[y[1:]]

            if (op := c[0]) == 'print':
                print(''.join(c[1:]))
            elif op == 'input':
                var['answer'] = input(c[1])
            elif op == 'make':
                var[c[1]] = c[2]
            elif op == 'if':
                x, y = int(c[1]), int(c[3])
                if (o := c[2]) == '>':
                    b = x > y
                elif o == '<':
                    b = x < y
                else:
                    b = c[1] == c[3]

                if not b:
                    ind = find(code, ind, op)
            elif op == 'loop':
                if int(c[1]):
                    c[1] = int(c[1]) - 1
                else:
                    ind = find(code, ind, op)
            elif op == 'endloop':
                ind = find(code, ind, op) + 1
        ind += 1


if __name__ == '__main__':
    f = open(sys.argv[1])
    data = f.readlines()
    f.close()

    run(data)
