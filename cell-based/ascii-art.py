import sys
import re


def find_bracket(symbols, num, mode):
    bracket = (1, -1)[mode == ']']
    while bracket:
        num = num + (1, -1)[mode == ']']
        if (symb := symbols[num]) in '[]':
            bracket += (1, -1)[symb == ']']
    return num


if __name__ == '__main__':
    with open(sys.argv[1]) as file:
        code = ''
        for line in file:
            code += re.sub(' *\n', '\n', line)
        code = [line for line in code.split('\n\n') if line.count('\n') < 6]

    bf = ''
    cells = [0]
    index = pointer = new = 0
    
    sym_dict = [
        {'-': '-'}, {'#': '.'}, {'|': ','}, {'\\': '<', '/': '>'},
        {'|': '+'}, {'_': '[', '|': ']'}
    ]

    for sym in code:
        try:
            bf += sym_dict[sym.count('\n')][sym[-1]]
        except KeyError as k:
            pass
    while index < len(bf):
        char = bf[index]
        if char in '<>':
            pointer = max(pointer + (1, -1)[char == '<'], 0)
            if char == '>' and pointer > len(cells) - 1:
                cells.append(0)
        elif char in '+-':
            cells[pointer] = (cells[pointer] + (1, -1)[char == '-']) % 256
        elif char == '.':
            print(chr(cells[pointer]), end='')
        elif char == ',':
            cells[pointer] = ord((input('\n' * new + 'Input: ') + chr(0))[0])
            new = True
        else:
            if ((cells[pointer] != 0) + (char == '[')) % 2:
                index = find_bracket(bf, index, char) - 1
        index += 1
