import sys
import re

point = sym = 0
reg = [0, 0]

if __name__ == '__main__':
    file = open(sys.argv[1]).readlines() + ['', '']
    code = re.sub('[^+~*]', '',  file[0])
    nums = re.sub('[^0-9]', ' ', file[1])
    nums = (nums + ' 0' * len(code)).split()

    while sym < len(code):
        op = code[sym]
        if op == '+':
            reg[point] += 1
        elif op == '~':
            if reg[point]:
                reg[point] -= 1
            else:
                sym = int(nums[sym]) - 1
        elif op == '*':
            point = not point
        sym += 1
