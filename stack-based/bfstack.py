import sys


def main():
    code = open(sys.argv[0]).read()
    line = []
    stack = [0]
    pointer = 0
    sym_dict = {
        '>': lambda: stack.append(0),
        '<': lambda: stack.pop(-1) if stack else 0,
        '+': lambda: stack.append((stack.pop(-1) + 1) % 256),
        '-': lambda: stack.append((stack.pop(-1) - 1) % 256),
        '.': lambda: print(chr(stack[-1]), end = ''),
        ',': lambda: stack.append(input('\nInput: ')) if line else stack.append(input('Input: ')) and line.append(0)
    }
    while pointer < len(code):
        if (char := code[pointer]) in sym_dict:
            sym_dict[char]()
        elif char in '[]':
            bracket = (-1, 1)[char == '[']
            while bracket:
                pointer += (-1, 1)[char == '[']
                if code[pointer] in '[]':
                    bracket += (-1, 1)[char == '[']
    pointer += 1


if __name__ == '__main__':
    main()
