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
    code = sub(r'[^><+-.,\][]', '', code)
    res = ('global _start\n'
           '_start:\n'
           '\tlea ecx, [esp - 6]\n'
           '\tmov edx, 1\n'
           '\tmov esi, 1\n\n')

    ins = {
        '>': ['right', False, False],
        '<': ['left', False, False],
        '.': ['output', False, False],
        ',': ['input', False, False]
    }

    ind = 0
    loop = 1
    arr = []

    while ind < len(code):
        num = count(code, ind)
        c = code[ind]

        if c in '><.,':
            if num > 1:
                res += f'\tmov esi, {num}\n'
                ins[c][2] = True
            res += f'\tcall {ins[c][0]}\n'

            ins[c][1] = True
        elif c in '+-':
            if n := num[0]:
                if n > 1:
                    res += f'\tadd byte [ecx], {n}\n'
                elif n == 1:
                    res += '\tinc byte [ecx]\n'
                elif n == -1:
                    res += '\tdec byte [ecx]\n'
                else:
                    res += f'\tsub byte [ecx], {-n}\n'

            ind = num[1]
            continue
        elif c in '[]':
            res += '\tcmp byte [ecx], 0\n'

            if c == '[':
                lab = loop if loop > 1 else ''
                arr.append(loop)
                loop += 1

                res += (f'\tje .bot{lab}\n'
                        f'.top{lab}:\n')
            else:
                lab = n if (n := arr.pop()) > 1 else ''

                res += (f'\tjne .top{lab}\n'
                        f'.bot{lab}:\n')

        ind += num

    res += ('\n\tmov eax, 1\n'
            '\txor ebx, ebx\n'
            '\tint 80h\n')

    def end(s, mul):
        return (mul * ('\tdec esi\n'
                       '\tcmp esi, 0\n'
                       f'\tjg {s}\n'
                       '\tinc esi\n')
                + '\tret\n')

    if ins['>'][1]:
        res += ('\nright:\n'
                '\tdec ecx\n'
                '\tmov byte [ecx], 0\n'
                + end('right', ins['>'][2]))
    if ins['<'][1]:
        res += ('\nleft:\n'
                '\tlea edi, [esp - 1]\n'
                '\tcmp ecx, edi\n'
                '\tje .done\n'
                '\tinc ecx\n')
        if ins['<'][2]:
            res += ('\tdec esi\n'
                    '\tcmp esi, 0\n'
                    '\tjg left\n'
                    '\tinc esi\n')
        res += ('.done:\n'
                '\tret\n')
    if ins['.'][1]:
        res += ('\noutput:\n'
                '\tmov eax, 4\n'
                '\tmov ebx, 1\n'
                '\tint 80h\n'
                + end('output', ins['.'][2]))
    if ins[','][1]:
        res += ('\ninput:\n'
                '\tmov eax, 3\n'
                '\txor ebx, ebx\n'
                '\tdec ecx\n'
                '\tint 80h\n'
                + end('input', ins[','][2]))

    return res


if __name__ == '__main__':
    f = open(sys.argv[1])
    data = f.read()
    f.close()

    f = open('output.txt', 'w')
    f.write(comp(data))
    f.close()
