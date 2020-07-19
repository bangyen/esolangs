file = open(__import__('sys').argv[1]).readlines()

point = cond = char = (vel := (0, 1))[0]
inst = (cells := [0]) * 2

funcs = [lambda n: cells.insert(0, n), cells.append]
code = [
    line + ' ' * (max(map(len, file)) - len(line))
    for line in file
]

while '*' in sum(code, []):
    char = code[inst[0]][inst[1]]
    if char == '*':
        break
    elif char in '\\/':
        mul = -1 ** (char == '/')
        vel = [k * mul for k in vel][::-1]
    elif char in '<>':
        point += -1 ** (char == '<')
        if not 0 <= point < len(cells):
            funcs[char == '>'](0)
            point = max(0, point)
    elif char == '-':
        cells[point] = not cells[point]
    mul = (not cells[point]) * (char == '+') + 1
    inst = [
        (inst[k] + vel[k] * mul)
        % len([code, code[0]][k]) for k in [0, 1]
    ]
