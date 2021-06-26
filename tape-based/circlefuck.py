import sys
import re


def parse(code):
    reg = re.compile(r'\\(?:\d\d\d|[\dA-F])')
    for s in reg.findall(code):
        if len(s) == 4:
            new = (oct(int(s[1:]))[2:]
                   .rjust(3, '0'))
        else:
            new = f'x0{s[1:]}'
        code = code.replace(s, f'\\{new}')

    code = (''.join(c for c in code if ord(c) < 127)
              .replace('\\ ', '\200')
              .replace('\\o', '\\'))
    code = (''.join(c for c in code if ord(c) > 32)
              .replace('\200', ' '))
    code = (bytes(code, 'utf-8')
            .decode('unicode_escape'))

    return [ord(c) for c in code]


def find(code, ind, mode):
    match = mode
    start = ind
    while match:
        ind = (ind + mode) % len(code)
        if ind == start:
            return -1
        if (sym := chr(code[ind])) == '[':
            match += 1
        elif sym == ']':
            match -= 1
    return ind


def run(code):
    code = parse(code)
    ind = ptr = 0
    new = False

    while True:
        if (char := chr(code[ind])) == '>':
            ptr = (ptr + 1) % len(code)
        elif char == '<':
            ptr = (ptr - 1) % len(code)
        elif char == '+':
            code[ptr] = (code[ptr] + 1) % 256
        elif char == '-':
            code[ptr] = (code[ptr] - 1) % 256
        elif char == '.':
            print(chr(code[ptr]), end='')
            new = True
        elif char == ',':
            val = input('\n' * new + 'Input: ')
            new = False
            if val:
                code[ptr] = ord(val[0])
        elif char == '[':
            if not code[ptr]:
                ind = find(code, ind, 1)
            if ind == -1:
                return
        elif char == ']':
            if code[ptr]:
                ind = find(code, ind, -1)
            if ind == -1:
                return
        elif char == '@':
            return
        elif char == '#':
            ind += 1
        elif char == '{':
            code.insert(ptr, 0)
            ind += 1
        elif char == '}':
            code.pop(ptr)

        ind = (ind + 1) % len(code)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
