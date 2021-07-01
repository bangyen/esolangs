import sys


def run(code):
    tape = [0] * 8
    ptr = ind = 0
    inp = 1

    while ind < len(code):
        ins = code[ind]
        if ins == '<' and ptr:
            ptr -= 1
        elif ins in '.[':
            ptr += 1
            if ptr + 1 >= len(tape):
                tape.append(0)
            tape[ptr] ^= 1

            if ins == '.':
                lst = map(str, tape[:8])
                if n := int(''.join(lst), 2):
                    print(chr(n), end='')
                    inp = 0
                else:
                    val = input('\nInput: '[inp:])
                    val = bin(ord(val[0]))[2:].zfill(8)
                    tape = [*map(int, val)] + tape[8:]
                    inp = 1
            else:
                if not tape[ptr]:
                    tape[ptr + 1] ^= 1
                    ind += 1

        ind += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
