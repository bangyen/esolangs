import sys


def add(pos, move, sym):
    x = (pos[0] + move[0]) % len(sym)
    y = (pos[1] + move[1]) % len(sym[0])
    return [x, y]


if __name__ == '__main__':
    funcs = [lambda n: cells.insert(0, n), cells.append]
    point = cond = char = (vel := (0, 1))[0]
    inst = (cells := [0]) * 2
    
    with open(sys.argv[1]).readlines() as file:
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
        elif char == '+':
            inst = add(inst, vel, code)
        inst = add(inst, vel, code)
