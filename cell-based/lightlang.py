bit = point = line = 0
vel = sym = 1

sym_dict = {
    '^': lambda: not bit,
    '!': lambda: print(bit + 0, end=''),
    '?': lambda: not input('\n' * line + 'Input: '),
    '@': lambda: __import__('random').choice([0, 1]),
    '&': lambda p: p + vel * bit,
    '<': lambda p: -1,
    '_': lambda: __import__('time').sleep(1)
}

code = open(__import__('sys').argv[1]).read()
while point < len(code) and (sym := code[point]) != '#':
    if sym in sym_dict:
        if (func := sym_dict[sym]).__code__.co_argcount:
            point = func(point)
        else:
            bit = bit if (f := func()) is None else f
            line = (sym == '?') or line
    vel *= (-1) ** (sym == '/')
    point += vel
