import sys
import re

line = []
halt = above = True
var = mole = move_num = 0
velocity = position = code = (0, 0)
directions = [(-1, 0), (0, 1), (1, 0), (0, -1)]

mole_dict = {
    '%': lambda m: ord((' ', '\n')[num]) if (num := value(position, code)) in [0, 1] else m,
    '=': lambda m: line.append(0) or ord(input('\n' * bool(line[1:]) + 'Input: ')[0]),
    ':': lambda m: print(m if m < 10 else chr(m), end='') or 0,
    '+': lambda m: m + value(position, code),
    '-': lambda m: m - value(position, code),
    '*': lambda m: m * value(position, code, num=1),
    '/': lambda m: m / value(position, code, num=1)
}


def move(pointer, direct):
    i = [0, pointer[0] + direct[0], len(code)][1]
    j = [0, pointer[1] + direct[1], len(code[0])][1]
    return i, j


def value(pointer, symbols, num=0):
    new_direct = directions[:]
    if pointer[0] == 0:
        new_direct.remove((-1, 0))
    if pointer[0] == max(len(code) - 2, 0):
        new_direct.remove((1, 0))
    if pointer[1] == 0:
        new_direct.remove((0, -1))
    if pointer[1] == len(code[0]) - 1:
        new_direct.remove((0, 1))
    chars = [
        symbols[i][j] for i, j in
        [move(pointer, pos) for pos in new_direct]
    ]
    return ([sym for sym in chars if type(sym) == int] + [num])[0]


if __name__ == '__main__':
    code = [
        [int(k) if k.isdigit() else k for k in re.sub(' *\n', '\n', line)]
        for line in open(sys.argv[1]).readlines()
    ]

    length = max(len(line) for line in code)
    code = tuple([line + [' '] * (length - len(line)) for line in code] + [['']])

    if (start := code[0][0]) in '\'>':
        velocity = ((start == '\'') + 0, (start == '>') + 0)
        halt = False

    while not halt:
        char = str(code[position[0]][position[1]])
        if above:
            halt = char == '@'
            if char in '><':
                velocity = (0, (-1, 1)[char == '>'])
            elif char in '\'^':
                velocity = ((-1, 1)[char == '\''], 0)
            elif char == '#':
                if (numb := value(position, code)) in [0, 1]:
                    velocity = directions[
                        (directions.index(velocity) + (-1, 1)[numb]) % 4
                        ]
            elif char == '$':
                above = False
                move_num = value(position, code) - 1
        else:
            if not move_num:
                move(position, velocity)
                above = True
                continue
            move_num -= 1
            if char in mole_dict:
                mole = mole_dict[char](mole)
            elif char == '~':
                mole = ''
                while not mole.isdigit():
                    mole = input('Input: ')[0]
                mole = int(mole)
            elif char == ';':
                val = mole
            elif str(char).isalnum() or char in '.,!?':
                mole = char if type(char) == int else ord(char)
        position = move(position, velocity)
