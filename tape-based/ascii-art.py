import sys
import re


def run(code):
    code = re.sub(' +\n', '\n', code)
    code = code.split('\n\n')

    bf = ''
    stk = []
    tape = [0]
    ind = ptr = 0
    new = False

    sym = {
        (0, '-'): '-', (1, '#'): '.',
        (2, '|'): ',', (3, '\\'): '<',
        (3, '/'): '>', (4, '|'): '+',
        (5, '_'): '[', (5, '|'): ']'
    }

    for c in code:
        t = (c.count('\n'), c[-1])
        if t in sym:
            bf += sym[t]

    while ind < len(bf):
        if (char := bf[ind]) == '>':
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
            new = True
        elif char == ',':
            val = input('\n' * new + 'Input: ')
            tape[ptr] = ord(val[0])
            new = False
        elif char == '[':
            if tape[ptr]:
                stk.append(ind)
            else:
                match = 1
                while match:
                    ind += 1
                    if ind == len(bf):
                        return
                    elif bf[ind] == '[':
                        match += 1
                    elif bf[ind] == ']':
                        match -= 1
        elif char == ']':
            ind = stk.pop() - 1

        ind += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
