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


def run(code):
    code = re.sub(r'[^\df(x)=+-^]', '', code)
    if code[:5] != 'f(x)=':
        return

    code = sanitize(code)
    code = [k for k in np.roots(code) if np.imag(k) >= 0]
    code = convert(code)

    ind = reg = 0
    new = 1
    sym = [
        lambda r, a: r + a, lambda r, a: r - a,
        lambda r, a: r * a, lambda r, a: r / a,
        lambda r, a: r % a, lambda r, a: r ** a,
        lambda: reg > 0, 0,
        lambda: reg < 0, lambda: not reg
    ]

    while ind < len(code):
        one, *rest = code[ind]
        if two := (rest + [0])[0]:
            if one:
                reg = sym[two - 1](reg, one)
            elif two - 1:
                val = input('\nInput: '[new:]) + chr(0)
                reg = ord(val[0]) or -1
                new = 1
            else:
                print(chr(max(0, reg)), end='')
                new = 0
        elif one in [2, 6]:
            beg = code[brackets(code, ind)][0]
            if beg > 4 and sym[(beg - 1) % 4 + 6]():
                ind = brackets(code, ind)
        elif not sym[(one % 4) + 5]():
            ind = brackets(code, ind)
        ind += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
