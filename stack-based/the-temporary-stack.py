import random
import sys
import re

integer = 1
stack = code = []
repeat = comment = 0
pointer = line = command = 0


def run(char):
    global pointer, line, integer
    global repeat, comment, command
    if comment:
        comment = char != ' '
        return
    if char == '@':
        string = input('\n' * line + 'Input: ')
        for ch in string:
            stack.append(ord(ch))
        line = True
    elif char == 'v':
        if nums := re.findall('^v[0-9]+', code[pointer:]):
            stack.append(int(nums[0][1:]))
    elif char == '*':
        if strings := re.findall(r'^\*[^ ]+', code[pointer:]):
            for ch in strings[0][1:]:
                stack.append(ord(ch))
    elif char in 'oO':
        integer = char == 'O'
    elif char == '+':
        stack.append(stack[-1])
    elif char == ':':
        pointer += 2
        length = len(stack)
        while len(stack) == length:
            run(code[pointer])
        command -= 1
    elif char == '\\':
        pointer += 2
        while len(stack):
            run(code[pointer])
        command -= 1
    elif char == '€':
        run(random.choice('@v*oO+:\\'))
    elif char == '#':
        comment = bool(re.findall('#[^ ]+', code[pointer:]))
    else:
        command -= 1
    while stack and sum(stack[1:]) / 2 > stack[0]:
        print((chr, lambda n: n)[integer](stack.pop(0) - 1), end=' ' * integer)


if __name__ == '__main__':
    code = open(sys.argv[1], encoding='utf-8').read()
    code = re.sub(' +', ' ', code)
    while pointer < len(code):
        run(code[pointer])
        pointer += 1
        command += 1
        if not command % 15:
            stack = []
