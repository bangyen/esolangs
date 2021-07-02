import sys
import re


def run(code):
    reg = re.compile(r'(\d+) *= *(\d+)')
    arr = {k: 0 for k in range(5)}
    num = ind = 0
    new = 1

    for m in reg.finditer(code[0]):
        x, y = m[1], m[2]
        if x == '42':
            x = input('Key: ')
        elif y == '42':
            y = input('Value: ')
            y = y if y else 0
        arr[int(x)] = int(y)

    code = code[1:]
    while num < 2:
        copy = arr.copy()
        expr = (r'(move *(-?\d+)'
                r' *(-?\d+)|sum)')

        if m := re.search(expr, code[ind]):
            if m[1] == 'sum':
                arr[0] = arr[1]
                for k in range(2, 5):
                    arr[0] += arr[k]
            else:
                if m[2].isdigit():
                    x = int(m[2])
                    n = arr.get(x, 0)

                    if m[3].isdigit():
                        y = int(m[3])
                        arr[y] = n
                    else:
                        print(n, end=' ')
                        new = 0
                elif m[3].isdigit():
                    y = int(m[3])
                    n = input('\nInput: '[new:])
                    arr[y] = int(n) if n else 0
                    new = 1

        num = (num + 1) * (arr == copy)
        ind = (ind + 1) % len(code)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
