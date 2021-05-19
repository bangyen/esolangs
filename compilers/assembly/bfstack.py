from re import sub
import sys


def count(code, ind):
    code += ' '
    num = 0

    if (start := code[ind]) in '+-':
        while (ins := code[ind]) in '+-':
            if ins == '+':
                num += 1
            else:
                num -= 1
            ind += 1
        return num, ind
    else:
        while code[ind] == start:
            num += 1
            ind += 1
        return num


def comp(code):
    res = 'global _start\n' \
        + '_start:\n' \
        + '\tlea ecx, [esp - 6]\n' \
        + '\tmov edx, 1\n\n'

    ins = {
        '>': ['right', False],
        '<': ['left', False],
        '.': ['output', False],
        ',': ['input', False]
    }

    ind = 0
    loop = 1
    arr = []

    while ind < len(code):
        num = count(code, ind)
        c = code[ind]

        if c in '><.,':
            if num > 1:
                res += f'\tmov edx, {num}\n'
            res += f'\tcall {ins[c][0]}\n'

            ins[c][1] = True
        elif c in '+-':
            if (n := num[0]) < 0:
                res += f'\tsub byte [ecx], {-n}\n'
            else:
                res += f'\tadd byte [ecx], {n}\n'

            ind = num[1]
            continue
        elif c in '[]':
            res += '\tcmp byte [ecx], 0\n'

            if c == '[':
                lab = loop if loop > 1 else ''
                arr.append(loop)
                loop += 1

                res += f'\tje bot{lab}\n' \
                    + f'top{lab}:\n'
            else:
                lab = n if (n := arr.pop()) > 1 else ''

                res += f'\tjne top{lab}\n' \
                       + f'bot{lab}:\n'

        ind += num

    res += '\n\tmov eax, 1\n' \
        + '\tmov ebx, 0\n' \
        + '\tint 0x80\n'

    def end(s):
        return '\tsub edx, 1\n' \
            + '\tcmp edx, 0\n' \
            + f'\tjg {s}\n' \
            + '\tmov edx, 1\n' \
            + '\tret\n'

    if ins['>'][1]:
        res += '\nright:\n' \
            + '\tsub ecx, 1\n' \
            + '\tmov byte [ecx], 0\n' \
            + end('right')
    if ins['<'][1]:
        res += '\nleft:\n' \
            + '\tlea edi, [esp - 1]\n' \
            + '\tcmp ecx, edi\n' \
            + '\tje done\n' \
            + '\tadd ecx, 1\n' \
            + end('left\ndone:')
    if ins['.'][1]:
        res += '\noutput:\n' \
            + '\tmov eax, 4\n' \
            + '\tmov ebx, 1\n' \
            + '\tint 0x80\n' \
            + end('output')
    if ins[','][1]:
        res += '\ninput:\n' \
            + '\tmov eax, 3\n' \
            + '\tmov ebx, 0\n' \
            + '\tsub ecx, 1\n' \
            + end('input')

    return res


if __name__ == '__main__':
    f = open(sys.argv[1])
    data = f.read()
    f.close()

    data = sub(r'[^><+-.,\][]', '', data)
    b = sub(r'[^\[\]]', '', data)

    while True:
        if '[]' in b:
            b = b.replace('[]', '')
        else:
            if b:
                print('Unmatched brackets.')
                exit(0)
            else:
                break

    f = open('output.txt', 'w')
    f.write(comp(data))
    f.close()
