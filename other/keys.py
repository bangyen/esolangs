import sys
import re

code = open(sys.argv[1]).readlines() + ['x', 'y']

if cond := ((zero := code[0].strip()) == code[1].strip()):
    cond = all(chars not in zero for chars in ['-_', '_-', '\\-', '/_'])
    cond = cond and not re.search(r'[^\\/\-_]', zero)
    
print(['Reject.', 'Accept.'][cond])
