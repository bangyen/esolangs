from re import sub
import sys


def count(code, ind):
    char = code[ind]
    code += ' '
    num = 0

    while code[ind] == char:
        num += 1
        ind += 1

    return num


def convert(code, num):
    code = sub('[^><.,!]', '', code)
    res = ('global _start\n'
           '_start:\n'
           f'\tmov ebx, {num}\n'
           '\txor esi, esi\n'
           '\tlea ecx, [esp - 12]\n'
           '\tlea edi, [ecx - 4]\n'
           '\tmov edx, 1\n'
           '.main:\n')
    length = len(code)

    ind = 0
    add = False
    inp = False
    out = False
    exc = False

    while ind < length:
        n = count(code, ind)
        c = code[ind]

        if c == '>':
            s = f'sub edi, {n * 4}'
        elif c == '<':
            s = ('add esi, [edi]\n'
                 '\tlea edi, [ecx - 4]')

            if n > 2:
                s += (f'\n\tmov edx, {n - 1}\n'
                      '\tcall left')
            else:
                s += ('\n\tadd esi, [edi]'
                      * (n - 1))

            add = True
        elif c == '.':
            s = 'output'
            out = True
        elif c == ',':
            s = 'input'
            inp = True
        else:
            s = ('call excl'
                 + f'\n\tadd DWORD [edi], {n - 1}'
                 * (n > 1))
            exc = True

        if c in '.,':
            s = '\n\t'.join(f'call {s}' for _ in range(n))
        res += f'\t{s}\n'

        ind += n

    res += ('\n\tdec ebx\n'
            '\tcmp ebx, 0\n'
            '\tjg .main\n'
            '\tmov eax, 1\n'
            '\txor ebx, ebx\n'
            '\tint 80h')

    if inp:
        res += ('\n\ninput:\n'
                '\tpush ebx\n'
                '\tmov eax, 3\n'
                '\txor ebx, ebx\n'
                '\tint 80h\n'
                '\tadd esi, [ecx]\n'
                '\tpop ebx\n'
                '\tret')
    if out:
        res += ('\n\noutput:\n'
                '\tcmp esi, 0\n'
                '\tje .done\n'
                '\tpush ebx\n'
                '\tdec esi\n'
                '\tpush esi\n'
                '\tmov eax, 4\n'
                '\tmov ebx, 1\n'
                '\tint 80h\n'
                '\tpop esi\n'
                '\tinc esi\n'
                '\tpop ebx\n'
                '.done:\n'
                '\tret')
    if exc:
        res += ('\n\nexcl:\n'
                '\tinc DWORD [edi]\n'
                '\tsub [edi], esi\n'
                '\tcmp DWORD [edi], 0\n'
                '\tjge .done\n'
                '\tmov DWORD [edi], 0\n'
                '.done:\n'
                '\txor esi, esi\n'
                '\tlea edi, [ecx - 4]\n'
                '\tret')
    if add:
        res += ('\n\nleft:\n'
                '\tpush ebx\n'
                '\tmov eax, edx\n'
                '\tmov ebx, [edi]\n'
                '\tmul ebx\n'
                '\tadd esi, eax\n'
                '\tmov edx, 1\n'
                '\tpop ebx\n'
                '\tret')

    return res


if __name__ == '__main__':
    loop = 1
    if len(sys.argv) > 2:
        try:
            loop = int(sys.argv[2])
        except ValueError:
            pass

    f = open(sys.argv[1])
    data = f.read()
    f.close()

    f = open("output.txt", "w")
    f.write(convert(data, loop))
    f.close()
