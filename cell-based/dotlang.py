import sys
import re

line = False
start = True
dots = [None]

velocity = [(0, 0)]
position = [(0, 0)]
directions = [(-1, 0), (0, 1), (1, 0), (0, -1)]


def move(pointer, direct):
    return pointer[0] + direct[0], pointer[1] + direct[1]


def swap(direct):
    index = directions.index(direct)
    return directions[index + (1, -1)[index % 2]]


if __name__ == '__main__':
    file = open(sys.argv[1], encoding='utf-8').readlines()
    lines = [re.sub(' *\n', '\n', line) for line in file]
    file = ''.join(file)

    length = max(len(line) for line in lines)
    lines = [line + ' ' * (length - len(line)) for line in lines] + [''] * length

    if file == ' ':
        print(' ')
        start = False
    else:
        for k in range(len(lines)):
            if '•' in lines[k]:
                position[0] = (k, lines[k].find('•'))
                if (x := lines[k].find('•')) != 0 and lines[k][x - 1] in '^>v<':
                    velocity[0] = directions['^>v<'.find(lines[k][x - 1])]
                else:
                    velocity[0] = directions[1]
                break
        else:
            start = False
    while start and dots:
        for k in range(len(position)):
            position[k] = move(position[k], velocity[k])
            if (pos := position[k])[0] >= len(lines) or pos[1] >= length:
                start = False
                break
            char = lines[pos[0]][pos[1]]
            if char in ' \n':
                for lst in [velocity, position, dots]:
                    lst.pop(k)
            elif char in '^>v<':
                velocity[k] = directions['^>v<'.find(char)]
            elif char == '#':
                lst = re.findall(r'#(?:\d+|\d+\.\d+|`.+`)', lines[pos[0]][pos[1]:])
                if lst:
                    dots[k] = lst[0][1:].replace('`', '')
                    if velocity[k] == (0, 1):
                        position[k] = (pos[0], pos[1] + len(dots[k]))
                else:
                    if dots[k]:
                        print(dots[k], end='')
                    else:
                        start = False
            elif char == '~':
                dots[k] = input('\n' * line + 'Input: ')
                line = True
            elif char == '(':
                temp = 0
                if lines[pos[0]][pos[1] + 1] == '`':
                    lst = re.findall(r'\(`\w+', lines[pos[0]][pos[1]:])
                    if lst:
                        name = ')' + lst[0][1:]
                        for ind, line in enumerate(lines):
                            if name in line:
                                temp = (ind, line.find(name))
                                break
                    else:
                        start = False
                else:
                    match = 1
                    temp = list(pos)
                    while match:
                        temp[1] += 1
                        if temp[1] == len(lines[0]):
                            start = False
                            break
                        elif lines[temp[0]][temp[1]] == '(':
                            match += 1
                        elif lines[temp[0]][temp[1]] == ')':
                            match -= 1
                dots.append(None)
                position.append(temp)
                velocity.append(velocity[k])
            elif char == 'W':
                if lines[pos[0]][pos[1] + 1] == '~':
                    warp = 'W%s`s' % input("\n" * line + "Warp: ")
                    if warp in file:
                        for ind, line in enumerate(lines):
                            if warp in line:
                                position[k] = (ind, line.find(warp))
                                if velocity[k] == (0, 1):
                                    position[k] = (position[k][0], position[k][1] + len(warp) - 1)
                                break
                    else:
                        start = False
                elif lst := re.findall(r'\w+`s', lines[pos[0]][pos[1]:]):
                    warp = lst[0][:-1] + 'e'
                    if warp in file:
                        for ind, line in enumerate(lines):
                            if warp in line:
                                position[k] = (ind, line.find(warp))
                                break
                    else:
                        start = False
            elif char in '!?:':
                func = [lambda s: s.isdigit(), lambda s: s.isalpha()][char == '!']
                if dots[k] and func(dots[k].replace('.', '', char == '?')):
                    velocity[k] = swap(velocity[k])
