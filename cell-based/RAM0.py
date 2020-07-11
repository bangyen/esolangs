import sys
import re

ram = {}
point = 0
reg = [0, 0]

sym_dict = {
    'C': lambda: point + (not reg[0]),
    'S': lambda: ram.update({reg[1]: reg[0]}),
    'A': lambda: reg.insert(0, reg.pop(0) + 1),
    'L': lambda: reg.insert(0, ram.get(reg.pop(0), 0)),
    'N': lambda: [reg.pop(1), reg.append(reg[0])][1],
    'Z': lambda: [reg.pop(0), reg.insert(0, 0)][1]
}

if __name__ == '__main__':
    code = [line.strip() + ' ' * 5 for line in open(sys.argv[1])]
    while point < len(code):
        if (char := code[point][0]) in sym_dict:
            point = sym_dict[char]() or point
        elif code[point][:5] == 'GOTO ':
            if nums := re.findall('GOTO [0-9]+', code[point]):
                point = max(-1, int(nums[0][5:]) - 2)
        point += 1
