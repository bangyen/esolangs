from inspect import signature


def convert(func):
    num = len(signature(func).parameters)
    total = 2 ** (num + 1) - 1
    lines = ['' for _ in range(total)]
    pos = [total // 2]

    for j in range(num + 1):
        if j < num:
            for k in range(total):
                if k in pos:
                    lines[k] += '>2$~;#@'
                else:
                    lines[k] += ' ' * 7
            pos = [i + 2 ** (num - j - 1) for i in pos] + \
                  [i - 2 ** (num - j - 1) for i in pos]
            for k in pos:
                lines[k] = lines[k][:-2] + '> '

        else:
            for k in range(2 ** num):
                arg_list = [0] * num + [int(i) for i in bin(k)[2:]]
                lines[k * 2] += f'>$3{func(*arg_list[-num:])}:@'

    lines[0] = '\'' + lines[0][1:]
    return '\n'.join(k for k in lines).replace('> >', '>  ')
