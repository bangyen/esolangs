import sys


def find(code, ind):
    if 'end' in (op := code[ind]):
        match = op[3:]
        move = -1
    else:
        match = 'end' + op
        move = 1

    num = move
    ind += move

    while num:
        if ind == len(code):
            return ind
        if code[ind][0] == op:
            num += move
        elif code[ind][0] == match:
            num -= move
        ind += move
    return ind - 1


def run(code):
    ind = 0
    var = {}
    skip = False

    for num, val in enumerate(code):
        val = (val.lstrip()
                  .rstrip('\n')
                  .split(','))

        code[num] = [
            v.replace('*44', ',')
            for v in val if v
        ]

    while ind < len(code):
        if (c := code[ind]) and not skip:
            for x, y in enumerate(c[1:]):
                if isinstance(y, str):
                    if y[0] == '$':
                        c[x] = var[y[1:].strip()]
                    if (isinstance(c[x], str)
                            and c[x].isdigit()):
                        c[x] = int(c[x])

            if (op := c[0]) == 'print':
                print(*c[1:], sep='')
            elif op == 'input':
                var['answer'] = input(c[1])
            elif op == 'make':
                if len(c) == 5:
                    if (o := c[3]) == '+':
                        v = c[2] + c[4]
                    elif o == '-':
                        v = c[2] - c[4]
                    elif o == '*':
                        v = c[2] * c[4]
                    else:
                        v = c[2] / c[4]
                    var[c[1]] = v
                else:
                    var[c[1]] = c[2]
            elif op == 'if':
                x, o, y = c[1:4]
                if o == '>':
                    b = x > y
                elif o == '<':
                    b = x < y
                else:
                    b = x == y
                if not b:
                    ind = find(code, ind)
            elif op == 'loop':
                if c[1]:
                    c[1] -= 1
                else:
                    ind = find(code, ind)
                    skip = False
            elif op == 'endloop':
                ind = find(code, ind) + 1
                skip = True
        ind += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
