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
    res = 'global _start\n' \
        '_start:\n' \
        f'\tmov ebx, {num}\n' \
        '\txor esi, esi\n' \
        '\tlea ecx, [esp - 12]\n' \
        '\tlea edi, [ecx - 4]\n' \
        '\tmov edx, 1\n' \
        'main:\n'
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
            s = 'add esi, [edi]\n' \
                '\tlea edi, [ecx - 4]'

            if n > 2:
                s += \
                    f'\n\tmov edx, {n - 1}\n' \
                    '\tcall left'
            else:
                s += (n - 1) * '\n\tadd esi, [edi]'

            add = True
        elif c == '.':
            s = 'output'
            out = True
        elif c == ',':
            s = 'input'
            inp = True
        else:
            s = 'call excl' \
                + (n > 1) * f'\n\tadd DWORD [edi], {n - 1}'
            exc = True

        if c in '.,':
            s = '\n\t'.join(f'call {s}' for _ in range(n))
        res += f'\t{s}\n'

        ind += n

    res += '\n\tsub ebx, 1\n' \
        '\tcmp ebx, 0\n' \
        '\tjg main\n' \
        '\tmov eax, 1\n' \
        '\tmov ebx, 0\n' \
        '\tint 0x80'

    if inp:
        res += '\n\ninput:\n' \
            '\tpush ebx\n' \
            '\tmov eax, 3\n' \
            '\tmov ebx, 0\n' \
            '\tint 0x80\n' \
            '\tadd esi, [ecx]\n' \
            '\tpop ebx\n' \
            '\tret'
    if out:
        res += '\n\noutput:\n' \
            '\tcmp esi, 0\n' \
            '\tje done_o\n' \
            '\tpush ebx\n' \
            '\tsub esi, 1\n' \
            '\tpush esi\n' \
            '\tmov eax, 4\n' \
            '\tmov ebx, 1\n' \
            '\tint 0x80 \n' \
            '\tpop esi\n' \
            '\tadd esi, 1\n' \
            '\tpop ebx\n' \
            'done_o:\n' \
            '\tret'
    if exc:
        res += '\n\nexcl:\n' \
            '\tadd DWORD [edi], 1\n' \
            '\tsub [edi], esi\n' \
            '\tcmp DWORD [edi], 0\n' \
            '\tjge done_e\n' \
            '\tmov DWORD [edi], 0\n' \
            'done_e:\n' \
            '\txor esi, esi\n' \
            '\tlea edi, [ecx - 4]\n' \
            '\tret'
    if add:
        res += '\n\nleft:\n' \
            '\tpush ebx\n' \
            '\tmov eax, edx\n' \
            '\tmov ebx, [edi]\n' \
            '\tmul ebx\n' \
            '\tadd esi, eax\n' \
            '\tmov edx, 1\n' \
            '\tpop ebx\n' \
            '\tret'

    return res


if __name__ == '__main__':
    loop = 1
    if len(sys.argv) > 2:
        try:
            loop = int(sys.argv[2])
        except ValueError:
            pass

    f = open(sys.argv[1])
    data = sub('[^><.,!]', '', f.read())
    f.close()
    
    f = open("output.txt", "w")
    f.write(convert(data, loop))
    f.close()
