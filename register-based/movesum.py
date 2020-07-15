import sys
import re

count = pointer = new = 0
cells = {k: 0 for k in range(5)}

if __name__ == '__main__':
    first, *code = re.sub(' *\n *', '\n', open(sys.argv[1]).read()).split('\n')

    if re.match('( *([0-9]+=-?[0-9]+) *)+', first):
        first = [
            [(int(n), '')[n == '42'] for n in eq.split('=')]
            for eq in first.split()
        ]
    else:
        first = code = []

    for x, y in first:
        while not str(x).isdigit():
            x = input('Key: ')
        while not str(y).isdigit():
            y = input('Value: ')
        cells[int(x)] = int(y)

    while code and count < 2:
        copy = cells.copy()
        func, one, two, *rest = f'{code[pointer]} | | |'.split()
        if func == 'move':
            if not (one.isdigit() or two.isdigit()):
                count += 1
                continue
            if '-' in one:
                while not one.isdigit():
                    one = input('\n' * new + 'Input: ')
                    new = True
                cells[int(two)] = int(one)
            else:
                if '-' in two:
                    print(f'{cells[int(one)]} ', end='')
                else:
                    val = cells[int(one)] if int(one) in cells else 0
                    cells[int(two) if two.isdigit() else -1] = val
        elif func == 'sum':
            cells[0] = sum(cells[k] for k in range(1, 5))
        count = (count + 1) * (cells == copy)
        pointer = (pointer + 1) % len(code)
