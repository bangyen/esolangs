import sys
import re


def parse(code):
    reg = (r'\\(?:\d\d\d|'
           r'[\dA-F](?:$|[^\d]))')
    exp = r'((^|[^\\]) |\\( )|(\\)o)'

    for s in re.findall(reg, code):
        if len(s) == 4:
            new = (oct(int(s[1:]))
                   [2:].zfill(3))
        else:
            new = f'x0{s[1:]}'
        code = code.replace(s, f'\\{new}')

    code = re.sub(exp, r'\2\3\4', code)
    code = ''.join(c for c in code if
                   31 < ord(c) < 127)
    code = (bytes(code, 'utf-8')
            .decode('unicode_escape'))

    return [ord(c) for c in code]


def find(code, ind, ptr):
    char = chr(code[ind])
    if char == '[':
        if code[ptr]:
            return ind
        mode = 1
    else:
        if not code[ptr]:
            return ind
        mode = -1

    match = mode
    start = ind
    num = len(code)

    while match:
        ind = (ind + mode) % num
        if ind == start:
            return -1

        sym = chr(code[ind])
        if sym == '[':
            match += 1
        elif sym == ']':
            match -= 1
    return ind


def run(code):
    code = parse(code)
    ind = ptr = 0
    new = 1

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
            val = chr(code[ptr])
            print(val, end='')
            new = 0
        elif char == ',':
            val = input('\nInput: '[new:])
            code[ptr] = ord(val[0])
            new = 1
        elif char in '[]':
            ind = find(code, ind, ptr)
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
