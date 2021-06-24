import random
import sys
import re


def run(code):
    code = re.sub(r'[^@v*oO+:\\€# ]', '', code)
    code = re.sub(' {2,}', ' ', code)

    stk = []
    num = True
    new = False
    ptr = comm = 0

    def match(reg):
        return (re.match(reg, code[ptr + 1:])
                  .group(0))

    def parse(char):
        nonlocal new, ptr, comm, num

        if char == '@':
            s = input('\n' * new + 'Input: ')
            stk.extend(ord(c) for c in s)
            new = False
        elif char == 'v':
            if n := match('[0-9]+'):
                stk.append(int(n))
            ptr += len(n)
        elif char == '*':
            if s := match('[^ ]+'):
                stk.extend(ord(c) for c in s)
            ptr += len(s)
        elif char in 'oO':
            num = char == 'O'
        elif char == '+':
            stk.append(stk[-1])
        elif char == ':':
            ptr += 2
            n = len(stk)
            while len(stk) == n:
                parse(code[ptr])
            comm += 1
        elif char == '\\':
            ptr += 2
            while len(stk):
                parse(code[ptr])
            comm += 1
        elif char == '€':
            parse(random.choice('@v*oO+:\\'))
        elif char == '#':
            n = len(match('[^ ]*'))
            ptr += n
            comm += n
        else:
            comm -= 1

        while stk and sum(stk[1:]) / 2 > stk[0]:
            new = True
            n = stk.pop(0) - 1
            print(n if num else chr(n), end='')

    while ptr < len(code):
        parse(code[ptr])
        ptr += 2
        comm += 1
        if comm % 15 == 0:
            stk = []


if __name__ == '__main__':
    f = open(sys.argv[1], encoding='utf-8')
    data = f.read()
    f.close()

    run(data)
