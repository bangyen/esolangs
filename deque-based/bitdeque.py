import sys

deque = []
point = reg = num = 0
code = open(sys.argv[1]).read().split()

sym_dict = {
    'PUSH': lambda: deque.append(reg),
    'INJECT': lambda: deque.insert(0, reg),
    'POP': lambda r: deque.pop(-1) if deque else 0,
    'EJECT': lambda r: deque.pop(0) if deque else 0,
    'INVERT': lambda r: not reg
}

while point < len(code):
    if (sym := code[point]) in sym_dict:
        count = (func := sym_dict[sym]).__code__.co_argcount
        reg = func(reg) if count else func() or reg
    elif sym == 'GOTO':
        if point < len(code) - 1 and (num := code[point + 1]).isdigit():
            point = max(-1, int(num) - 2) if reg else point
    point += 1
