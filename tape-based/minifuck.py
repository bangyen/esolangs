import sys


def run(code):
    tape = [0] * 8
    ptr = ind = 0
    inp = False

    while ind < len(code):
        ins = code[ind]
        if ins == '<':
            ptr = max(ptr - 1, 0)
        elif ins in '.[':
            ptr += 1
            if ptr + 1 >= len(tape):
                tape.append(0)
            tape[ptr] ^= 1

            if ins == '.':
                if n := int(''.join(str(k) for k in tape[:8]), 2):
                    print(chr(n), end='')
                    inp = True
                else:
                    val = input('\n' * inp + 'Input: ')
                    val = '0' * 8 + bin(ord((val + '\0')[0]))[2:]
                    tape = [int(k) for k in val[-8:]] + tape[8:]

                    inp = False
            else:
                if not tape[ptr]:
                    tape[ptr + 1] ^= 1
                    ind += 1

        ind += 1


if __name__ == '__main__':
    f = open(sys.argv[1])
    data = f.read()
    f.close()

    run(data)
