import secrets
import sys


def run(code):
    code = code.split()

    stk = []
    num = True
    new = False
    ptr = comm = 0

    def parse(char):
        nonlocal new, ptr, comm, num
        rest = code[ptr][1:]

        if char == '@':
            s = input('\n' * new + 'Input: ')
            stk.extend(ord(c) for c in s)
            new = False
        elif char == 'v':
            stk.append(int(rest))
        elif char == '*':
            stk.extend(ord(c) for c in rest)
        elif char in 'oO':
            num = char == 'O'
        elif char == '+':
            stk.append(stk[-1])
        elif char == ':':
            ptr += 1
            n = len(stk)
            while len(stk) == n:
                parse(code[ptr][0])
            comm += 1
        elif char == '\\':
            ptr += 1
            while len(stk):
                parse(code[ptr][0])
            comm += 1
        elif char == '€':
            parse(secrets.choice('@v*oO+:\\'))

        while stk and sum(stk[1:]) / 2 > stk[0]:
            new = True
            n = stk.pop(0) - 1
            print(n if num else chr(n), end='')

    while ptr < len(code):
        parse(code[ptr][0])
        ptr += 1
        comm += 1
        if comm % 15 == 0:
            stk = []


if __name__ == '__main__':
    f = open(sys.argv[1], encoding='utf-8')
    data = f.read()
    f.close()

    run(data)
