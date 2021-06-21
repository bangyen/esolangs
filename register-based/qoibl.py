import sys
import re


def run(code):
    line = False
    var = {}

    def parse(expr):
        nonlocal line

        if (op := expr[0]) == 'tt':
            print(chr(parse(expr[1:-1])), end='')
            line = True
        elif op == 'we':
            ind = expr.index('we', 1)
            var[parse(expr[1:ind])] \
                = parse(expr[ind + 1:-1])
        elif op == 'rr':
            ind = expr.index('rr', 1)
            while parse(expr[1:ind]):
                parse(expr[ind + 1:-1])
        elif 'yr' in expr:
            beg = expr.index('yr')
            num = expr[beg + 1]
            x = parse(expr[:beg])
            y = parse(expr[beg + 3:])

            if num == 'ee':
                return x == y
            elif num == 'ey':
                return x > y
            elif num == 'ye':
                return x < y
            elif num == 'yy':
                return x != y
        elif 'ry' in expr:
            beg = expr.index('ry')
            num = expr[beg + 1]
            x = parse(expr[:beg])
            y = parse(expr[beg + 3:])

            if num == 'ee':
                return x + y
            elif num == 'ey':
                return x - y
            elif num == 'ye':
                return x * y
            elif num == 'yy':
                return x // y
        elif op == 'qe':
            return var.get(parse(expr[1:-1]), 0)
        elif op == 'et':
            n = input('\n' * line + 'Input: ')
            line = False
            return ord(n[0])
        elif re.fullmatch('[ey]+', op):
            op = (op.replace('e', '0')
                    .replace('y', '1'))
            return int(op, 2)

    for exp in code:
        parse(exp.split())


if __name__ == '__main__':
    f = open(sys.argv[1])
    data = f.readlines()
    f.close()

    run(data)
