import sys
import re


def find(code, ind):
    opr = code[ind]
    end = chr(ord(opr) + 2)
    match = 1

    while match:
        ind += 1
        if ind == len(code):
            break
        elif (c := code[ind]) == opr:
            match += 1
        elif c == end:
            match -= 1
    return ind


def run(code):
    acc = ind = 0
    skp = False
    stk = []
    new = 1

    while ind < len(code):
        if (c := code[ind]) == '[':
            if skp:
                ind = find(code, ind)
            else:
                stk.append(ind)
        elif c in ']*':
            ind = stk.pop() - 1
            if c == '*':
                skp = True
        elif c == '.':
            print(acc, end='')
            new = 0
        elif c == ':':
            num = input('\nInput: '[new:])
            new = 1
            if num.isdigit():
                acc = int(num)
        elif c == ',':
            print(chr(acc), end='')
            new = 0
        elif c == ';':
            val = input('\nInput: '[new:])
            new = 1
            if val:
                acc = ord(val[0])
        elif c == '{':
            ind = find(code, ind)
        elif c == '&':
            return
        else:
            val = code[ind:]
            if m := re.match(r'@\$(\d+){', val):
                n = m.end() - 1
                if acc == int(m[1]):
                    ind += n
                else:
                    ind = find(code, ind + n) + 1
            elif m := re.match(r'@\$?(.){', val):
                n = m.end() - 1
                if acc == ord(m[1]):
                    ind += n
                else:
                    ind = find(code, ind + n) + 1
            elif m := re.match(r'#\$(\d+)', val):
                acc = int(m[1])
                ind += m.end() - 1
            elif m := re.match(r'#\$?(.)', val):
                acc = ord(m[1])
                ind += m.end() - 1

        ind += 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
