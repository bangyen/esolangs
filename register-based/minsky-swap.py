import sys
import re


def run(text):
    ind = ptr = val = 0
    reg = [0, 0]
    nums = []
    code = ''

    if re.match('[+~*]', text):
        code = (s := text.split('\n'))[0]
        code = re.sub('[^+~*]', '', code)
        if len(s) > 1:
            nums = re.findall(r'\d+', s[1])
            nums = [int(k) for k in nums]
    else:
        cmp = r'(inc|swap|decnz)\((\d*)\);'
        cmp = re.compile(fr'(?:^|\W){cmp}')
        for m in cmp.findall(text):
            if (s := m[0][0]) == 'i':
                code += '+'
            elif s == 's':
                code += '*'
            else:
                code += '~'
                skip = int(m[1])
                nums.append(skip)

    while ind < len(code):
        if (op := code[ind]) == '+':
            reg[ptr] += 1
        elif op == '~':
            if reg[ptr]:
                reg[ptr] -= 1
            else:
                ind = nums[val] - 2
            val += 1
        elif op == '*':
            ptr ^= 1

        ind += 1
    print(*reg)


if __name__ == '__main__':
    if len(sys.argv[1]) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
