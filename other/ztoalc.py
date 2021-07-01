import sys


def run(code):
    ptr = int(code[0])
    inp = False
    var = {}

    def val(exp):
        nonlocal inp

        if exp == 'input':
            s = ord(input('\n' * inp + 'Input: ')[0])
            inp = False
            return s
        elif exp in var:
            return var.get(exp)
        elif exp.isnumeric():
            return int(exp)
        elif exp[0] == '-' and exp[1:].isnumeric():
            return int(exp)
        elif exp[0] == '[':
            return [0] * val(exp[1:-1])
        else:
            arg = exp[:-1].split('[')
            return var[arg[0]][val(arg[1])]

    while p := ptr - 1:
        ins = code[p] if p < len(code) else ''
        lst = ins.split()

        if 'print' in ins:
            print(chr(val(lst[1])), end='')
            inp = True
        elif 'jump' in ins:
            if val(lst[2]):
                ptr += 1
                continue
        elif ' =' in ins:
            var[lst[0]] = val(lst[2])
        elif '+' in ins:
            var[lst[0]] += val(lst[2])
        elif '-' in ins:
            var[lst[0]] -= val(lst[2])

        if ptr % 2:
            ptr = 3 * ptr + 1
        else:
            ptr //= 2


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
