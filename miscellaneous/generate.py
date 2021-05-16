def translate(s):
    res = '>>!' * 12 + '\n'

    for c in s:
        n = ord(c) + 1
        a = int(n ** 0.5)
        b = n // a
        c = n % a

        res += f'{a * "!"}{c * ">!"}><{b * "<"}.!>><>!\n'
    return res.strip()
