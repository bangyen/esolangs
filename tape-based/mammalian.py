import sys
import re


def run(code):
    ins = (
        'SEED',    'EXCRETE',
        'CONSUME', 'FISSION',
        'SPRINT',  'LEAPFROG',
        'DIGEST',  'CONFLAGRATE',
        'ACCEPT',  'PRONOUNCE'
    )

    code = re.findall(f'({"|".join(ins)})', code)
    lst = [[0] for _ in range(23)]
    ind = ptr = acc = 0
    new = 1

    while ind < len(code):
        curr = lst[ptr]
        if (n := ins.index(code[ind])) == 0:
            for num in range(23):
                lst[num][0] += num + 1
                lst[num][0] %= 256
        elif n == 1:
            curr.append(acc % 256)
            acc = 0
        elif n == 2:
            m = (len(curr) - 1) // 2
            acc = curr.pop(m)
        elif n == 3:
            m = (len(curr) - 1) // 2
            num = curr.pop(m) // 2
            curr.insert(0, num)
            curr.append(num)
        elif n == 4:
            if acc < len(curr):
                ptr = (ptr + curr[acc]) % 23
        elif n == 5:
            if curr[-1]:
                ind = acc - curr[0] - 1
        elif n == 6:
            acc ^= sum(curr)
        elif n == 7:
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
        elif n == 8:
            val = input('\nInput: '[new:])
            new = 1
            if val:
                m = ord(val[0]) ^ acc
                lst[0].append(m % 256)
        else:
            print(chr(acc % 256), end='')
            new = 0

        ind += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
