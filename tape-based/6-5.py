import sys
import re


def num(char):
    if char.isdigit():
        return int(char)
    return ord(char.upper()) - 55


def run(code):
    code = f' {code}'
    code = re.sub('([^78])C[^\n]*', '\1', code)

    cell = ind = 0
    tape = [0]
    line = 1

    while ind < len(code):
        if (c := code[ind]) == '1':
            cell += 2
            while len(tape) < cell + 1:
                tape.append(0)
        elif c == '3' and cell:
            cell -= 1
        elif c in '56':
            tape[cell] += int(c)
        elif c in '29':
            tape[cell] -= int(c) % 6 + 3
        elif c == '8':
            val = num(code[ind + 1])
            reg = f'([^4]*4){val}'
            if m := re.match(reg, code):
                ind = m.end() - 1
        elif c == '7':
            val = num(code[ind + 1])
            if tape[cell] == val:
                ind += 1
        elif c == '0':
            return
        elif c == 'A':
            print(chr(tape[cell]), end='')
            line = 0
        elif c == 'B':
            val = input('\nInput: '[line:])
            tape[cell] = ord(val[0])
            line = 1

        ind += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
