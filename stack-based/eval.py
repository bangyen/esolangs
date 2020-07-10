import sys
import re


def run(symbols):
    stacks = [[], []]
    pointer = st_point = 0

    sym_dict = {
        '`': lambda: stacks[st_point].append(not st_point),
        '^': lambda: stacks[st_point].append(stacks[st_point][-1]),
        '0': lambda: stacks[st_point].append(0),
        '+': lambda: stacks[st_point].append(stacks[st_point].pop(-1) + 1),
        '-': lambda: stacks[st_point].append(stacks[st_point].pop(-1) - 1),
        '.': lambda: print(stacks[st_point].pop(-1), end=''),
        ';': lambda: stacks[st_point].pop(-1),
        '=': lambda: stacks[not st_point].append(stacks[st_point].pop(-1))
    }

    while pointer < len(symbols):
        char = symbols[pointer]
        before, after = symbols[:pointer + 1], symbols[pointer + 1:]
        if char in sym_dict:
            sym_dict[char]()
        elif char == '~':
            st_point = not st_point
        elif char == '*':
            stacks[st_point] = stacks[st_point][::-1]
        elif char == '?':
            symbols = f'{before}{after[not stacks[st_point].pop(-1):]}'
        elif char == '!':
            symbols = f'{before}{stacks[st_point].pop(-1)}{after}'
        elif char == '"':
            string = re.findall('"[^"]*"', symbols[pointer:])[0].replace('`', '"')[1:-1]
            stacks[st_point].append(string)
            pointer += len(string) + 1
        elif char == '\'':
            stacks[st_point].insert(0, '"')
            stacks[st_point].append('"')
            symbols = f'{before}"{after}'
        pointer += 1


if __name__ == '__main__':
    run(open(sys.argv[1]).read())
