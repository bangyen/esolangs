import sys
import re


def find_bracket(symbols, num, mode):
    bracket = (1, -1)[mode == ']']
    original = num
    while bracket:
        num = (num + (1, -1)[mode == ']']) % len(symbols)
        if num == original:
            return
        if (sym := chr(symbols[num])) in '[]':
            bracket += (1, -1)[sym == ']']
    return num


if __name__ == '__main__':
    num_list = [
        r'\\[0-9]{3}', r'\\o[0-7]{3}',
        r'\\x[0-9A-Fa-f]{2}', r'\\[0-9A-F]'
    ]
    sub_dict = {
        r'\\': '\\', r'\ ': ' ', r'\n': '\n',
        r'\r': '\r', r'\t': '\t', r'\b': '\b'
    }
    with open(sys.argv[1]) as file:
        code = file.read().replace('%s', '%\\s') \
                          .replace('\n', '')
        for k in range(len(lst := re.findall(f'({"|".join(num_list)})', code))):
            item = lst[k]
            new = item.replace('\\', '').replace('x', '').replace('o', '')
            code = code.replace('|', '\\|').replace(item, f'|{k}|')
            num_list.append(int(new, [16, 16, 10, 8][len(item) - 2 - (item[1] == 'x')]))
        for key in sub_dict:
            code = code.replace(key, sub_dict[key])
        code = [
            [num_list[int(k) + 4]] if k.isdigit()
            else list(k.replace('%\\s', '%s'))
            for k in code.split('|')
        ]
        code = [k if type(k) == int else ord(k) for k in sum(code, [])]

    index = pointer = new = 0

    while index < len(code):
        char = chr(code[index])
        if char in '<>':
            pointer = (pointer + (1, -1)[char == '<']) % len(code)
        elif char in '+-':
            code[pointer] = (code[pointer] + (1, -1)[char == '-']) % 256
        elif char == '.':
            print(chr(code[pointer]), end='')
        elif char == ',':
            code[pointer] = ord((input('\n' * new + 'Input: ') + chr(0))[0])
            new = True
        elif char in '[]':
            if ((code[pointer] != 0) + (char == '[')) % 2:
                index = find_bracket(code, index, char)
                if index is None:
                    break
                else:
                    index -= 1
        elif char in '@':
            break
        elif char == '#':
            index += 1
        elif char in '{}':
            code.insert(pointer, 0) if char == '{' else code.pop(pointer)
            index += (char == '{')
        index += 1
