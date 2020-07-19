code = open(__import__('sys').argv[1]).readlines() + ['x', 'y']
if cond := ((zero := code[0].strip()) == code[1].strip()):
    cond = all(chars not in zero for chars in ['-_', '_-', '\\-', '/_'])
    cond = cond and not __import__('re').search(r'[^\\/\-_]', zero)
print(['Reject.', 'Accept.'][cond])
