import itertools
import sys
import re


def interpret(code):
    pointer = temp = 0
    output = False
    while pointer < len(code):
        sym = code[pointer]
        if sym in ['#', '@']:
            output = sym == '#'
        elif sym == '>':
            if output:
                print(chr(temp), end='')
            temp = 0
        elif sym == '|':
            num = code[pointer + 1]
            if isinstance(num, int):
                temp *= num
                pointer += 1
        elif isinstance(sym, int):
            temp += sym
        pointer += 1


with open(sys.argv[1]) as file:
    data = re.sub(r'[^\+|!>#@]', '', file.read())
    data = [''.join(g) for _, g in itertools.groupby(data)]
    data = [len(k) if k[0] == '+' else k for k in data]
    interpret(data)
