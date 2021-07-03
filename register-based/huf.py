import sys
import re


def run(code):
    code = re.findall(
        '#[^#@]+@', code)
    code = ''.join(code)
    num = mul = 0

    for sym in code:
        if sym == '#':
            num = mul = 0
        elif sym == '>':
            val = chr(num)
            print(val, end='')
            num = 0
        elif sym == '|':
            mul = 1
        elif sym == '!':
            num *= (mul - 1)
            mul = 0
        elif sym == '+':
            if mul:
                mul += 1
            else:
                num += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
