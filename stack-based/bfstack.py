import sys


def main():
    with open(sys.argv[1]) as file:
        code = file.read()
    line = []
    stack = [0]
    pointer = 0
    sym_dict = {
        '>': lambda: stack.append(0),
        '<': lambda: stack.pop(-1) if stack else 0,
        '+': lambda: stack.append((stack.pop(-1) + 1) % 256),
        '-': lambda: stack.append((stack.pop(-1) - 1) % 256),
        '.': lambda: print(chr(stack[-1]), end=''),
        ',': lambda: stack.append(ord((input('\n' * bool(line) + 'Input: ') + chr(0))[0])) or line.append(0)
    }
    while pointer < len(code):
        if (char := code[pointer]) in sym_dict:
            sym_dict[char]()
        elif char in '[]':
            if (stack[-1] != 0) - (char == '['):
                bracket = (-1, 1)[char == '[']
                while bracket:
                    pointer += (-1, 1)[char == '[']
                    if code[pointer] in '[]':
                        bracket += (-1, 1)[code[pointer] == '[']
        pointer += 1


if __name__ == '__main__':
    main()
