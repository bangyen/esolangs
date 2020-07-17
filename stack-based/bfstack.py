code = open(__import__('sys').argv[1]).read()

line = [1]
stack = [0]
pointer = 0

sym_dict = {
    '>': lambda: stack.append(0),
    '<': lambda: stack.pop(-1) if stack else 0,
    '+': lambda: stack.append((stack.pop(-1) + 1) % 256),
    '-': lambda: stack.append((stack.pop(-1) - 1) % 256),
    '.': lambda: print(chr(stack[-1]), end='') or line.append(0),
    ',': lambda: stack.append(ord((input('\nInput: '[line[-1]:]) + '\0')[0]))
}

while pointer < len(code):
    char = code[pointer]
    x = sym_dict[char]() if char in sym_dict else 0
    cond = char in '[]' and (stack[-1] != 0) - (char == '[')
    bracket = (-1, 1)[char == '['] if cond else 0
    while bracket:
        pointer += (-1, 1)[char == '[']
        bracket += (-1, 1)[code[pointer] == '['] \
            * (code[pointer] in '[]')
    pointer += 1
