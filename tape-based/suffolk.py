import sys


def run(code, limit=10):
    tape = [0]
    num = ind = 0
    ptr = acc = 0
    new = 1

    while num < limit:
        if (sym := code[ind]) == '>':
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif sym == '<':
            acc += tape[ptr]
            ptr = 0
        elif sym == '!':
            val = tape[ptr] + 1 - acc
            tape[ptr] = max(0, val)
            ptr = acc = 0
        elif sym == ',':
            inp = input('\nInput: '[new:])
            acc = acc + ord(inp[0]) if inp else 0
            new = 1
        elif sym == '.' and acc:
            val = chr(acc - 1)
            print(val, end='')
            new = 0

        ind += 1
        if ind == len(code):
            ind = 0
            num += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            if len(sys.argv) > 2:
                run(data, int(sys.argv[2]))
            else:
                run(data)
