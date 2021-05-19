def suffolk(s):
    res = '>>!' * 12 + '\n'

    for c in s:
        n = ord(c) + 1
        a = int(n ** 0.5)
        b = n // a
        c = n % a

        res += f'{a * "!"}{c * ">!"}><{b * "<"}.!>><>!\n'
    return res.strip()


def bfstack(text):
    res = '>\n'
    acc = 0

    for c in text:
        if abs(n := (ord(c) - acc)) < ord(c) + 3:
            if n > 0:
                res += '+' * n + '.\n'
            else:
                res += '-' * -n + '.\n'
        else:
            res += f'[-]{"+" * ord(c)}.\n'

        acc = ord(c)

    return res


def container(text):
    ins = ''
    ind = last = 0

    for c in text:
        if (o := ord(c) - last) >= 0:
            ins += f'+{o} A>={ind}\n' \
                   + f'-{o} A>={ind + 1}\n'
        else:
            ins += f'-{-o} A>={ind}\n' \
                   + f'+{-o} A>={ind + 1}\n'
        last = ord(c)
        ind += 2

    res = 'A:\n' \
        + '+1 EXIT>=1\n\n' \
        + 'PRINT:\n' \
        + '+1 PRINT<=0\n' \
        + '-1 PRINT>=1\n\n' \
        + 'OUT:\n' \
        + f'{ins}\n' \
        + 'EXIT=1:\n' \
        + '-1 A>=' \
        + str(2 * len(text) - 2)

    return res
