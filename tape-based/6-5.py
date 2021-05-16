import sys
import re


def num(char):
    if char.isalpha():
        return ord(char.upper()) - 55
    elif char.isdigit():
        return int(char)


def main(code):
    point = cell = 0
    tape = [0]
    line = 1

    while point < len(code):
        inst = code[point]
        if inst == '1':
            cell += 2
            while len(tape) < cell + 1:
                tape.append(0)
        elif inst == '3':
            cell -= 1 * (cell > 0)
        elif inst == '6':
            tape[cell] += 6
        elif inst == '5':
            tape[cell] += 5
        elif inst == '9':
            tape[cell] -= 6
        elif inst == '2':
            tape[cell] -= 5
        elif inst == '8':
            val = num(code[point + 1])
            point = 0
            while code[:point].count('4') != val:
                if point == len(code):
                    break
        elif inst == '7':
            if tape[cell] == num(code[point + 1]):
                point += 1
        elif inst == '0':
            break
        elif inst == 'A':
            print(chr(tape[cell]), end='')
            line = 0
        elif inst == 'B':
            inp = input('\nInput: '[line:]) + '\0'
            tape[cell] = ord(inp[0])

        point += 1


if __name__ == '__main__':
    s = f' {open(sys.argv[1]).read()}\n'
    s = re.sub('([^78])C[^\n]*\n', '\1', s)
    main(re.sub('[^0-9A-Z]', '', s))
