import sys

ins = cells = [0, 0]
vel = [(point := 0), 1]

file = open(sys.argv[1]).readlines()
size = max(len(lst) for lst in file)
code = [(line + ' ' * size)[:size] for line in file]


def add(pos, move, sym):
    x = (pos[0] + move[0]) % len(sym)
    y = (pos[1] + move[1]) % len(sym[0])
    return [x, y]


while char := code[ins[0]][ins[1]]:
    if char == '*':
        break
    elif char in '\\/':
        mul = -1 ** (char == '/')
        vel = [k * mul for k in vel][::-1]
    elif char in '<>':
        point += -1 ** (char == '<')
        if not 0 <= point < len(cells):
            if char == '>':
                cells.append(0)
            else:
                cells.insert(0, 0)
            point = max(0, point)
    elif char == '-':
        cells[point] = not cells[point]
    elif char == '+':
        ins = add(ins, vel, code)
    ins = add(ins, vel, code)
