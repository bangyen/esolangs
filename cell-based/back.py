velocity = (0, 1)
pointer = cond = char = 0
instruct = (cells := [0]) * 2

code = [list(line) for line in open(__import__('sys').argv[1]).readlines()]
code = [line + [' '] * (max(len(lst) for lst in code) - len(line)) for line in code]

while '*' in sum(code, []) and (char := code[instruct[0]][instruct[1]]) != '*':
    if char in '\\/':
        velocity = [k * (-1, 1)[char == '\\'] for k in (velocity[1], velocity[0])]
    if char in '<>':
        pointer += (-1, 1)[char == '>']
        if not 0 <= pointer < len(cells):
            if char == '>':
                cells.append(0)
            else:
                cells.insert(0, 0)
                pointer = max(0, pointer)
    cells[pointer] = (cells[pointer] + (char == '-')) % 2
    cond = (not cells[pointer]) * (char == '+')
    for k in (0, 1):
        instruct[k] += velocity[k] * (cond + 1)
        instruct[k] = instruct[k] % len((code, code[0])[k])
