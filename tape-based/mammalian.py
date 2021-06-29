import sys
import re


def total(op, lst):
    if op:
        size = list(map(len, lst))
        flat = sum(lst, [])
        m = len(flat)

        for k in range(m // 2):
            x, y = flat[k], flat[m - k - 1]
            n = m - k - 1

            if x > y:
                num = x // y
                flat[k] -= num
                flat[n] = (x + num) % 256
            elif x < y:
                num = y % x
                flat[k] += num
                flat[n] -= num

        for k in range(23):
            lst[k] = flat[:size[k]]
            flat = flat[size[k]:]
    else:
        for num in range(23):
            lst[num][0] += num + 1
            lst[num][0] %= 256


def partial(op, curr, acc):
    if op == 2:
        curr.append(acc % 256)
        acc = 0
    elif op == 3:
        m = (len(curr) - 1) // 2
        acc = curr.pop(m)
    elif op == 4:
        m = (len(curr) - 1) // 2
        num = curr.pop(m) // 2
        curr.insert(0, num)
        curr.append(num)
    else:
        acc ^= sum(curr)

    return acc


def run(code):
    ins = (
        'SEED',    'CONFLAGRATE',
        'EXCRETE', 'CONSUME',
        'FISSION', 'DIGEST',
        'SPRINT',  'LEAPFROG',
        'ACCEPT',  'PRONOUNCE'
    )

    code = re.findall(f'({"|".join(ins)})', code)
    lst = [[0] for _ in range(23)]
    ind = ptr = acc = 0
    new = 1

    while ind < len(code):
        n = ins.index(code[ind])
        curr = lst[ptr]
        if n < 2:
            total(n, lst)
        elif n < 6:
            acc = partial(n, curr, acc)
        elif n == 6 and acc < len(curr):
            ptr = (ptr + curr[acc]) % 23
        elif n == 7 and curr[-1]:
            ind = acc - curr[0] - 1
        elif n == 8:
            val = input('\nInput: '[new:])
            new = 1
            if val:
                m = ord(val[0]) ^ acc
                lst[0].append(m % 256)
        elif n == 9:
            print(chr(acc % 256), end='')
            new = 0

        ind += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
