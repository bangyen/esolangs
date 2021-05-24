from re import sub
import sys


def count(code, ind):
    code += ' '
    num = 0

    if (start := code[ind]) in 'as':
        while (ins := code[ind]) in 'as':
            if ins == 'a':
                num += 1
            else:
                num -= 1
            ind += 1
    else:
        while code[ind] == start:
            num += 1
            ind += 1

    return num, ind


def comp(code):
    res = ''

    func = {
        'd': ['down', False, False],
        'f': ['right', False, False],
        'k': ['print', False, False]
    }

    reg = {
        '[^asdfjkl;]': '',
        '([^j])k{2,}': r'\1k',
        ';{2,}': ';',
        '^((dddd)+|(ffff)+|k*j[^l]|k*l[^l]*l|k+)': '',
        '([^j])((dddd)+|(ffff)+)': r'\1',
        '([^j]k)(j[^l]|l[^l]*l)': r'\1'
    }

    for x, y in reg.items():
        code = sub(x, y, code)

    skip = ind = 0
    end = False
    loop = 1

    while ind < len(code):
        num, new = count(code, ind)
        c = code[ind]

        if c in 'as':
            if ind and code[ind - 1] == 'j':
                num = 1 if c == 'a' else -1
                new = ind + 1

            if num > 1:
                res += f'\tadd dword [ecx], {num}\n'
            elif num == 1:
                res += f'\tinc dword [ecx]\n'
            elif num == -1:
                res += f'\tdec dword [ecx]\n'
            elif num < -1:
                res += f'\tsub dword [ecx], {-num}\n'
        elif c in 'dfk':
            if ind and code[ind - 1] == 'j':
                num, new = 1, ind + 1

            if num != 1:
                res += f'\tmov eax, {num}\n'
                func[c][2] = True
            res += f'\tcall {func[c][0]}\n'
            func[c][1] = True
        elif c == 'j':
            skip += 1
            ind = new
            end = True

            n = skip if skip - 1 else ""
            res += '\tcmp dword [ecx], 0\n' \
                   f'\tje .skip{n}\n'

            continue
        elif c == 'l':
            loop += 1
            n = m if (m := (loop // 2 - 1)) else ""
            res += '\tcmp dword [ecx], 0\n'

            if loop % 2:
                res += f'\tjne .top{n}\n' \
                       f'.bot{n}:\n'
            else:
                res += f'\tje .bot{n}\n' \
                       f'.top{n}:\n'
        elif c == ';':
            res += '\n\tmov eax, 1\n' \
                   '\txor ebx, ebx\n' \
                   '\tint 80h\n'

        if end:
            n = skip if skip - 1 else ""
            res += f'.skip{n}:\n'
            end = False
        ind = new

    def cell(r):
        return '\tmov eax, 20\n' \
               f'\tmul {r}\n' \
               '\tlea ecx, [esp + eax]\n' \
               '\tlea ecx, [ecx + 4*esi]\n' \
               '\tmov eax, 1\n'

    if func['d'][1]:
        if func['d'][2]:
            s = '\tadd edi, eax\n' \
                '\tand edi, 3\n'
        else:
            s = '\tinc edi\n' \
                '\tand edi, 3\n'

        if func['k'][1]:
            s += '\tmov ebx, edi\n' \
                 '\tcall cell\n'
        else:
            s += cell('edi')

        res += '\ndown:\n' \
               + s \
               + '\tret\n'
    if func['f'][1]:
        if func['f'][2]:
            s = '\tadd esi, eax\n' \
                '\tand esi, 3\n'
        else:
            s = '\tinc esi\n' \
                '\tand esi, 3\n'

        if func['d'][1]:
            s += '\tmov ebx, esi\n' \
                 '\tcall cell\n'
        else:
            s += cell('esi')

        res += '\nright:\n' \
               + s \
               + '\tret\n'
    if func['k'][1]:
        b = func['k'][2]
        res += '\nprint:\n' \
               + '\tpush eax\n' * b \
               + '\tmov eax, 4\n' \
               + '\tmov ebx, 1\n' \
               + '\tmov edx, 1\n' \
               + '\tint 80h\n' \
               + '\tmov dword [ecx], 0\n' \
               + ('\tpop eax\n'
                  '\tdec eax\n'
                  '\tcmp eax, 0\n'
                  '\tjg print\n'
                  '\tinc eax\n') * b \
               + '\tmov eax, 1\n' * (1 - b) \
               + '\tret\n'

    if func['d'][1] and func['f'][1]:
        res += '\ncell:\n' \
               + cell('ebx') \
               + '\tret\n'

    s = 'global _start\n' \
        '_start:\n' \
        '\tlea esp, [esp - 100]\n' \
        '\tmov ecx, esp\n' \
        '\txor edi, edi\n' \
        '\txor esi, esi\n'

    if any(func[c][2] for c in 'dfk'):
        s += '\tmov eax, 1\n'

    return (f'{s}\n' + res).replace('\n\n\n', '\n\n')


if __name__ == '__main__':
    f = open(sys.argv[1])
    data = f.read()
    f.close()

    f = open('output.txt', 'w')
    f.write(comp(data))
    f.close()
