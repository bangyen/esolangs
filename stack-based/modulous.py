import random
import sys
import re


def run(code):
    code = code[1:-1].split('][')
    var = {f'VAR{k}': 0 for k in range(1, 5)}

    line = False
    inp = True
    ind = 0
    stk = []

    while ind < len(code):
        mod = code[ind]
        ind += 1

        if 'INP' not in mod:
            inp = True

        arg = mod.split()

        if 'JMP' in mod:
            cond = True
            val = stk[-1] if stk else 0

            if 'NIF' in mod or 'IF NOT' in mod:
                cond = val != int(arg[-1])
            elif 'IF' in mod:
                cond = val == int(arg[-1])

            ind += cond * (int(arg[2]) * (1 if arg[1] == 'F' else -1) - 1)
        elif 'ADD' in mod:
            stk[-1] += int(arg[1])
        elif 'SUB' in mod:
            stk[-1] -= int(arg[1])
        elif 'RST' == mod:
            ind = -1
        elif 'PSH' in mod:
            if 'INT' in mod:
                stk.append(int(arg[2]))
            elif 'STR' in mod:
                stk += [ord(c) for c in mod.split('"')[1]][::-1]
            elif 'VAR' in mod:
                var[arg[1]] = stk[-1]
        elif 'POP' == mod:
            stk.pop()
        elif 'SWP' == mod:
            stk.append(stk.pop(-2))
        elif 'PRT' in mod:
            if 'VAR' in mod:
                n = var[arg[1]]
            else:
                n = stk.pop()

            print(n if 'INT' in mod else chr(n), end='')
        elif 'INP' in mod:
            n = input('\n' * (line and inp) + 'Input: ')
            line = True
            inp = False

            if 'INT' in mod:
                while not n.isnumeric():
                    n = input('\n' * (line and inp) + 'Input: ')
                stk.append(int(n))
            else:
                stk += [ord(c) for c in n][::-1]
        elif 'END' == mod:
            break
        elif 'DUP' == mod:
            stk.append(stk[-1])
        elif 'RND' in mod:
            stk.append(random.randint(0, int(arg[1])))
        elif '+' in mod:
            arg = mod.split('+')
            var[arg[0]] += int(arg[1])
        elif '-' in mod:
            arg = mod.split('-')
            var[arg[0]] += int(arg[1])


if __name__ == '__main__':
    if len(a := sys.argv) > 1:
        file = open(a[1])
    else:
        file = None
        print('First argument must be a file name.')
        exit(0)

    data = file.read()
    data = re.sub(r'][^\[\]]+\[', '][', data)

    if not re.match(r'^\[.+]*$', data):
        print('Unmatched brackets.')
        exit(0)

    run(data)
