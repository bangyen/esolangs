import numpy as np
import sys
import re


def prime(number):
    for val in range(2, int(np.sqrt(number)) + 1):
        if not number % val:
            return False
    return True


def brackets(string, pointer):
    length = len(string[pointer]) == 1
    end = string[pointer][0] in [2, 6]
    direct = (1, -1)[length and end]
    count = direct
    while count:
        pointer += direct
        if len(string[pointer]) == 1:
            if string[pointer][0] in [2, 6]:
                count -= 1
            else:
                count += 1
    return pointer


def convert(pre):
    pre = [np.round(k) for k in pre]
    pre = sorted(pre, key=lambda x: np.imag(x) or x)
    post = []
    num = 2

    while pre:
        if not prime(num):
            num += 1
            continue
        for root in pre:
            if im := np.imag(root):
                for val in range(1, 7):
                    # to the power of, not multiply
                    if im == num ** val:
                        pre.remove(root)
                        post.append([int(np.real(root)), val])
                        break
            else:
                for val in range(1, 9):
                    if root == num ** val:
                        pre.remove(root)
                        post.append([val])
                        break
        num += 1
    return post


def sanitize(code):
    code = code[5:].replace('x^0', '')
    reg_dict = {
        r'^x': '1x', r'(\D)x': r'\g<1>1x',
        r'x([+-])': r'x^1\1',
    }
    for regex in reg_dict:
        code = re.sub(regex, reg_dict[regex], code)

    code = code + 'x^0'
    mono = re.findall(r'-?\d+x\^\d+', code)
    post = []

    for k in range(int(mono[0].split('x^')[1]) + 1):
        for m in mono:
            if k == int((nums := m.split('x^'))[1]):
                post.insert(0, int(nums[0]))
                mono.remove(m)
                break
        else:
            post.insert(0, 0)
    return post


if __name__ == '__main__':
    file = re.sub('[ \n]', '', open(sys.argv[1]).read())
    if file[:5] != 'f(x)=':
        exit()

    const = sanitize(file)
    roots = [k for k in np.roots(const) if np.imag(k) >= 0]
    inst = convert(roots)

    point = reg = line = 0
    sym_list = [
        lambda r, a: r + a, lambda r, a: r - a, lambda r, a: r * a,
        lambda r, a: r / a, lambda r, a: r % a, lambda r, a: r ** a
    ]

    while point < len(inst):
        one, *rest = inst[point]
        if two := (rest + [0])[0]:
            if one:
                reg = sym_list[two - 1](reg, one)
            else:
                if two - 1:
                    string = input('\n' * line + 'Input: ') + chr(0)
                    reg = ord(string[0]) or -1
                    line = 1
                else:
                    print(chr(max(0, reg)), end='')
        else:
            cond = [lambda: reg > 0, 0, lambda: reg < 0, lambda: not reg]
            if one in [2, 6]:
                if (beg := inst[brackets(inst, point)][0]) > 4 and cond[(beg - 1) % 4]():
                    point = brackets(inst, point)
            else:
                if not cond[(one % 4) - 1]():
                    point = brackets(inst, point)
        point += 1
