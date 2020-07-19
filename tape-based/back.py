from sys import argv

pointer = cond = char = 0
inst = (cells := [0]) * 2
vel = (0, 1)

code = [list(line) for line in open(argv[1]).readlines()]
code = [line + [' '] * (max(len(lst) for lst in code) - len(line)) for line in code]
funcs = [lambda n: cells.insert(0, n), cells.append]

while '*' in sum(code, []) and (char := code[inst[0]][inst[1]]) != '*':
    if char in '\\/':
        vel = [k * (-1, 1)[char == '\\'] for k in (vel[1], vel[0])]
    elif char in '<>':
        pointer += (-1, 1)[char == '>']
        if not 0 <= pointer < len(cells):
            funcs[char == '>'](0)
            pointer = max(0, pointer)
    cells[pointer] = (cells[pointer] + (char == '-')) % 2
    for k in (0, 1):
        inst[k] += vel[k] * ((not cells[pointer]) * (char == '+') + 1)
        inst[k] = inst[k] % len((code, code[0])[k])
