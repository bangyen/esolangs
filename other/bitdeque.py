import sys
import re


def run(code):
    expr = re.compile(r'GOTO *(\d+)')
    code = expr.sub('GOTO\1', code)
    code = code.split()
    ind = reg = 0
    deq = []

    while ind < len(code):
        sym = code[ind]
        if sym == 'PUSH':
            deq.append(reg)
        elif sym == 'INJECT':
            deq.insert(0, reg)
        elif sym == 'POP':
            reg = (deq.pop() if
                   deq else 0)
        elif sym == 'EJECT':
            reg = (deq.pop(0) if
                   deq else 0)
        elif (m := expr.search(sym)
                and reg):
            ind = int(m[1]) - 1
        elif sym == 'INVERT':
            reg ^= 1

        ind += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
