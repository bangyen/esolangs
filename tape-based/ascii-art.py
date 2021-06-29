import sys
import re


def parse(code):
    code = re.sub(' +\n', '\n', code)
    code = code.split('\n\n')
    res = ''
    sym = {
        (0, '-'): '-', (1, '#'): '.',
        (2, '|'): ',', (3, '\\'): '<',
        (3, '/'): '>', (4, '|'): '+',
        (5, '_'): '[', (5, '|'): ']'
    }

    for c in code:
        t = (c.count('\n'), c[-1])
        if t in sym:
            res += sym[t]
    return res


def run(code):
    code = parse(code)
    tape = [0]

    ind = ptr = 0
    stk = []
    new = 1

    while ind < len(code):
        if (char := code[ind]) == '>':
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif char == '<' and ptr:
            ptr -= 1
        elif char in '+':
            tape[ptr] = (tape[ptr] + 1) % 256
        elif char == '-':
            tape[ptr] = (tape[ptr] - 1) % 256
        elif char == '.':
            print(chr(tape[ptr]), end='')
            new = 0
        elif char == ',':
            val = input('\nInput: '[:new])
            tape[ptr] = ord(val[0])
            new = 1
        elif char == '[':
            if tape[ptr]:
                stk.append(ind)
            else:
                match = 1
                while match:
                    ind += 1
                    if ind == len(code):
                        return
                    elif code[ind] == '[':
                        match += 1
                    elif code[ind] == ']':
                        match -= 1
        elif char == ']':
            ind = stk.pop() - 1

        ind += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
