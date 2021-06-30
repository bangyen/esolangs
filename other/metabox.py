import sys
import re


def find(code, ind):
    reg = '(┌─*┐|╭─*╮|╔═*╗)'
    mat = re.search(reg, code)
    x = mat.start()
    y = mat.end()

    def extend(s):
        m = s[1] * (y - x)
        return s[0] + m + s[2]

    if mat.group()[0] == '╔':
        side = '║.*║$'
        done = '╚═╝'
    else:
        side = '│.*│$'
        if mat.group()[0] == '┌':
            done = '└─┘'
        else:
            done = '╰─╯'

    side = re.compile(side)
    done = extend(done)
    top = ind

    while True:
        c = code[ind][x:y]
        ind += 1

        if ind == len(code):
            return
        elif c == done:
            break
        elif not side.match(c):
            return

    return top, ind + 1, x, y


def inner(code, num):
    dim = find(code, num)
    if not dim:
        return

    x = dim[0] + 1
    y = dim[1] - 1
    a = dim[2] + 1
    b = dim[3] - 1
    lst = []

    for c in code[x:y]:
        lst.append(c[a:b])

    return lst


def delete(code, ind):
    dim = find(code, ind)
    if not dim:
        return

    x = dim[0]
    y = dim[1]
    a = dim[2]
    b = dim[3]

    while x < y:
        val = ' ' * (b - a)
        code[x] = (code[:x]
                   + val
                   + code[y:])
        x += 1


def run(code):
    var = {}

    def parse(lst):
        nonlocal code
        for num, val in enumerate(lst):
            if re.search('(┌─*┐|╭─*╮)', val):
                if len(v := find(lst, num)) == 1:
                    parse(v)
            else:
                s = ''.join(lst)
                if 'set variable' in s:
                    ...
                elif 'end program' in s:
                    break

    parse(code)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
