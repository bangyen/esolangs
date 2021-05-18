def convert(text):
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
