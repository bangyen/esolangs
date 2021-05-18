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
