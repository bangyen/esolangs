import random
import sys
import re

line = []
halt = above = True
var = mole = move_num = 0
velocity = position = (0, 0)
directions = code = [(-1, 0), (0, 1), (1, 0), (0, -1)]

mole_dict = {
    '%': lambda m: ord((' ', '\n')[num]) if (num := value(position, code)) in [0, 1] else m,
    '=': lambda m: line.append(0) or ord(input('\n' * bool(line[1:]) + 'Input: ')[0]),
    ':': lambda m: print(m if m < 10 else chr(m), end='') or 0,
    '+': lambda m: m + value(position, code),
    '-': lambda m: m - value(position, code),
    '*': lambda m: m * value(position, code, num=1),
    '/': lambda m: m / value(position, code, num=1)
}


def move(pointer, symbols, direct):
    i = [0, pointer[0] + direct[0], len(symbols)][1]
    j = [0, pointer[1] + direct[1], len(symbols[0])][1]
    return i, j


def value(pointer, symbols, num=0):
    temp = directions[:]
    new_direct = [
        temp[0] * (pointer[0] != 0),
        temp[1] * (pointer[1] != len(symbols[0]) - 1),
        temp[2] * (pointer[0] != max(len(symbols) - 2, 0)),
        temp[3] * (pointer[1] != 0)
    ]
    chars = [
        symbols[i][j] for i, j in
        [move(pointer, symbols, pos) for pos in [k for k in new_direct if k]]
    ]
    return ([sym for sym in chars if type(sym) == int] + [num])[0]


def main(die=False):
    global code, velocity, halt, position, above, move_num, mole
    code = [
        [int(k) if k.isdigit() else k for k in re.sub(' *\n', '\n', code_line)]
        for code_line in open(sys.argv[1]).readlines()
    ]

    prob = random.randint(20, 90)
    length = max(len(code_line) for code_line in code)
    code = tuple([code_line + [' '] * (length - len(code_line)) for code_line in code] + [['']])

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
                if die:
                    chance = random.randint(1, 100)
                    if chance <= prob:
                        print('\nYou died.')
                        break
                above = False
                move_num = value(position, code) - 1
        else:
            if not move_num:
                move(position, code, velocity)
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
        position = move(position, code, velocity)


if __name__ == '__main__':
    main()
