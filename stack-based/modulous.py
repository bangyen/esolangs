import secrets
import sys
import re


def run(code):
    reg = re.compile(r'\[([^\[\]\"]*("[^"]*")?)]')
    code = [k[0] for k in reg.findall(code)]
    var = {f'VAR{k}': 0 for k in range(1, 5)}

    stk = []
    new = 1
    ind = 0

    while ind < len(code):
        mod = code[ind]
        arg = mod.split()
        ind += 1

        if 'JMP' in mod:
            cond = True
            val = stk[-1] if stk else 0

            if 'NIF' in mod:
                cond = val != int(arg[-1])
            elif 'IF' in mod:
                cond = val == int(arg[-1])

            if cond:
                if arg[1] == 'F':
                    ind += int(arg[2]) - 1
                else:
                    ind -= int(arg[2]) + 1
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
                m = mod.split('"')[1]
                stk += [ord(c) for c in m][::-1]
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

            if 'INT' in mod:
                print(n, end='')
            else:
                print(chr(n), end='')
            new = 0
        elif 'INP' in mod:
            n = input('\nInput: '[new:])
            new = 1

            if 'INT' in mod and n:
                stk.append(int(n))
            else:
                stk += [ord(c) for c in n][::-1]
        elif 'END' == mod:
            return
        elif 'DUP' == mod:
            stk.append(stk[-1])
        elif 'RND' in mod:
            n = secrets.randbelow(int(arg[1]))
            stk.append(n)
        elif '+' in mod:
            arg = mod.split('+')
            var[arg[0]] += int(arg[1])
        elif '-' in mod:
            arg = mod.split('-')
            var[arg[0]] += int(arg[1])


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
