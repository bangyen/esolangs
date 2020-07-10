pointer = cond = char = 0
instruct = cells = [0, 0]
directions = [(-1, 0), velocity := (0, 1), (1, 0), (0, -1)]

code = [list(line) for line in open(__import__('sys').argv[1]).readlines()]
code = [line + [' '] * (max(len(lst) for lst in code) - len(line)) for line in code]

while '*' in sum(code, []) and (char := code[instruct[0]][instruct[1]]) != '*':
    if cond:
        continue
    index = (directions.index(velocity) + (-1, 1)[char == '\\']) % 4
    velocity = directions[index] if char in '\\/' else velocity
    if char in ['<', '>']:
        pointer += (-1, 1)[char == '>']
        if not 0 <= pointer < len(cells):
            pointer = [lambda n: cells.insert(0, n), cells.append][char == '>'](0) or max(0, pointer)
    cells[pointer] = (cells[pointer] + (char == '-')) % 2
    cond = not cells[pointer] if char == '+' else 0
    instruct = [(instruct[k] + velocity[k]) % len(code[0] if k else code) for k in (0, 1)]
