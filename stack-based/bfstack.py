code = open(__import__('sys').argv[1]).read()

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
    char = code[pointer]
    x = sym_dict[char]() if char in sym_dict else 0
    cond = char in '[]' and (stack[-1] != 0) - (char == '[')
    bracket = (-1, 1)[char == '['] if cond else 0
    while bracket:
        pointer += (-1, 1)[char == '[']
        bracket += (-1, 1)[code[pointer] == '[']
            * (code[pointer] in '[]')
    pointer += 1
