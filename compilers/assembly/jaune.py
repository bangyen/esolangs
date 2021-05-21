from re import sub, findall
import sys


def count(code, ind):
    def check(k, s):
        ch = code[k]
        return ch.isnumeric() or ch in s

    start = code[ind]
    code += ' '
    num = 0

    if start in '+-':
        if (n := code[ind - 1]).isnumeric():
            num = int(start + code[ind - 1])
            while check(ind, '+-'):
                x, y = code[ind:ind + 2]
                if x.isnumeric() and y in '+-':
                    num += int(y + x)
                ind += 1
        else:
            return n, ind + 1
    elif start in ':$@':
        num = int(code[ind - 1])
        ind += 1
    elif start in '?!':
        num = int(code[ind - 1])
        while check(ind, '?!'):
            ind += 1
    else:
        while code[ind] == start:
            num += 1
            ind += 1

    return num, ind


def comp(code):
    for c in ':$':
        r = fr'(?:\d{c}){{2,}}'
        for s in findall(r, code):
            lst = [k for k in s if k.isnumeric()]
            m = str(min(int(k) for k in lst))
            op = '?!' if c == ':' else '@'

            for n in lst:
                for k in op:
                    code = code \
                        .replace(n + k, m + k)

            code = code.replace(s, m + c)

    ind = 0
    res = 'global _start\n' \
        '_start:\n' \
        '\tlea ecx, [esp - 60]\n' \
        '\tmov edx, 1\n' \
        '\txor edi, edi\n' \
        '\tmov esi, 1\n\n'
    subr = {
        '^': ['output', False, False],
        'v': ['input', False, False],
        '<': ['left', False, False],
        '&': ['mult', False, False]
    }

    while ind < len(code):
        c = code[ind]
        num, new = count(code, ind)

        if c in '^v<':
            if num > 1:
                res += f'\tmov esi, {num}\n'
                subr[c][2] = True
            res += f'\tcall {subr[c][0]}\n'
            subr[c][1] = True
        elif c == '&':
            if num > 1:
                res += f'\tmov esi, {num}\n' \
                    f'\tcall {subr[c][0]}\n'
                subr[c][1] = subr[c][2] = True
            else:
                res += '\tadd [ecx], edi\n'
        elif c == '>':
            res += f'\tsub ecx, {4 * num}\n'
        elif c in '+-':
            if num:
                if isinstance(num, int):
                    if num > 1:
                        res += f'\tadd dword [ecx], {num}\n'
                    elif num == 1:
                        res += '\tinc dword [ecx]\n'
                    elif num == -1:
                        res += '\tdec dword [ecx]\n'
                    else:
                        res += f'\tsub dword [ecx], {-num}\n'
                else:
                    if c == '+':
                        res += '\tadd [ecx], eax\n'
                    else:
                        res += '\tsub [ecx], eax\n'
        elif c == '#':
            res += '\tmov edi, [ecx]\n'
        elif c == ':':
            res += f'label{num}:\n'
        elif c == '?':
            res += '\tcmp dword [ecx], 0\n' \
                f'\tjne label{num}\n'
        elif c == '!':
            res += '\tcmp dword [ecx], 0\n' \
                f'\tje label{num}\n'
        elif c == '.':
            res += '\n\tmov eax, 1\n' \
                '\txor ebx, ebx\n' \
                '\tint 80h\n'
        elif c == '$':
            res += f'sub{num}:\n'
        elif c == '@':
            res += f'\tcall sub{num}\n'
        elif c == ';':
            res += '\tret\n'
        elif c == '%':
            res += '\tmov dword [ecx], 0\n'

        ind = new

    def end(opr):
        if subr[opr][2]:
            mul = '\tdec esi\n' \
                  '\tcmp esi, 0\n' \
                  f'\tjg {subr[opr][0]}\n' \
                  '\tinc esi\n' \
                  '\tret\n'
        else:
            mul = '\tret\n'
        return mul

    if subr['^'][1]:
        res += '\noutput:\n' \
               + '\tmov edi, [ecx]\n' \
               + '\tpush edi\n' \
               + '\n\tmov eax, 10\n' \
               + '\tcmp edi, 0\n' \
               + '\tjge .max\n' \
               + '\n\tmov dword [ecx], \'-\'\n' \
               + '\tcall print\n' \
               + '\tneg edi\n' \
               + '.max:\n' \
               + '\tcmp eax, edi\n' \
               + '\tjg .main\n' \
               + '\tmov ebx, 10\n' \
               + '\tmul ebx\n' \
               + '\tjmp .max\n' \
               + '.main:\n' \
               + '\txor edx, edx\n' \
               + '\tmov ebx, 10\n' \
               + '\tdiv ebx\n' \
               + '\n\txchg eax, edi\n' \
               + '\tdiv edi\n' \
               + '\tmov [ecx], eax\n' \
               + '\tmov eax, edx\n' \
               + '\txchg eax, edi\n' \
               + '\n\tadd dword [ecx], \'0\'\n' \
               + '\tcall print\n' \
               + '\tsub dword [ecx], \'0\'\n' \
               + '\n\tcmp eax, 1\n' \
               + '\tje .done\n' \
               + '\tjmp .main\n' \
               + '.done:\n' \
               + '\tpop edi\n' \
               + '\tmov [ecx], edi\n' \
               + end('^') \
               + '\nprint:\n' \
               + '\tpush eax\n' \
               + '\tmov eax, 4\n' \
               + '\tmov ebx, 1\n' \
               + '\tmov edx, 1\n' \
               + '\tint 80h\n' \
               + '\tpop eax\n' \
               + '\tret\n'
    if subr['v'][1]:
        s = '\ninput:\n' \
           + '\tpush ecx\n' \
           + '\tmov eax, 3\n' \
           + '\tmov ebx, 0\n' \
           + '\tlea ecx, [esp - 4]\n' \
           + '\tint 80h\n' \
           + '\tmov eax, [esp - 4]\n' \
           + '\tsub eax, \'0\'\n' \
           + end('v')
        res += s.replace('ret', 'pop ecx\n\tret')
    if subr['<'][1]:
        res += '\nleft:\n' \
               '\tlea ecx, [ecx + 4*esi]\n' \
               '\tlea eax, [esp - 48]\n' \
               '\tcmp eax, ecx\n' \
               '\tjge .done\n' \
               '\tmov ecx, eax\n' \
               '.done:\n' \
               '\tret\n'
    if subr['&'][1]:
        res += '\nmult:\n' \
               + '\tmov eax, edi\n' \
               + '\tmul esi\n' \
               + '\tadd [ecx], eax\n' \
               + '\tret\n'

    return res.replace('\n\n\n', '\n\n')


if __name__ == '__main__':
    f = open(sys.argv[1])
    data = f.read()
    f.close()

    data = sub(r'([#.;%])\1+', r'\1', data)
    f = open('output.txt', 'w')
    f.write(comp(data))
    f.close()
