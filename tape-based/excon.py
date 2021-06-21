import sys

pool, cell = ([0] * 8, 7)
code = open(sys.argv[1]).read()

for sym in code:
    if sym == ':':
        pool, cell = ([0] * 8, 7)
    elif sym == '^':
        pool[cell] ^= 1
    elif sym == '!':
        num = ''.join(map(str, pool))
        print(chr(int(num, 2)), end='')
    elif sym == '<':
        cell -= 1
