import sys


def run(code):
    pool, cell = ([0] * 8, 7)

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


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
