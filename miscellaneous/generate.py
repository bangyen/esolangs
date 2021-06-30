def bfstack(text):
    res = '>\n'
    acc = 0

    for c in text:
        n = ord(c) - acc
        if abs(n) < ord(c) + 3:
            o = '+' if n > 0 else '-'
            res += o * abs(n) + '.\n'
        else:
            o = "+" * ord(c)
            res += f'[-]{o}.\n'
        acc = ord(c)

    return res


def brainif(text):
    res = ''
    acc = 0

    for c in text:
        if (n := ord(c)) < acc:
            res += f'\nif {acc} move right\n'
            for k in range(n):
                res += f'if {k} increment\n'
            res += f'if {n} output\n'
        else:
            res += '\n'
            for k in range(acc, n):
                res += f'if {k} increment\n'
            res += f'if {n} output\n'
        acc = ord(c)

    return res.strip()


def container(text):
    ind = last = 0
    if text:
        res = ('A:\n'
               '+1 EXIT>=1\n\n'
               'PRINT:\n'
               '+1 PRINT<=0\n'
               '-1 PRINT>=1\n\n'
               'OUT:\n')
    else:
        return ('EXIT=1:\n'
                f'-1 EXIT>=0')

    for c in text:
        if (o := ord(c) - last) >= 0:
            res += (f'+{o} A>={ind}\n'
                    f'-{o} A>={ind + 1}\n')
        else:
            res += (f'-{-o} A>={ind}\n'
                    f'+{-o} A>={ind + 1}\n')
        last = ord(c)
        ind += 2

    res += ('EXIT=1:\n'
            f'-1 A>={ind - 2}')

    return res


def suffolk(text):
    res = ''
    num = 0

    for c in text:
        n = ord(c) + 1
        a = int(n ** 0.5)
        b = (n // a) * '<'
        c = (n % a) * '>!'
        if a > num:
            num = a
        res += (f'{a * "!"}{c}'
                f'><{b}.!>><>!\n')

    return ('>>!' * num
            + '\n' + res[-1:])


def _123(text):
    res = ''
    last = 0

    for c in text:
        b = (bin(ord(c) ^ last)[2:]
             .rjust(8, '0')
             .rstrip('0'))
        s = (b.replace('0', '2')
              .replace('1', '122'))

        if n := len(b):
            res += (f'{s[:-2]}'
                    f'{"121" * n}'[:-1]
                    + '\n')
        else:
            res += '12112\n'
        last = ord(c)

    return res + '1'
