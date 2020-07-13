import sys

tape = [0]
limit = 10
count = instruct = 0
pointer = internal = line = 0

if __name__ == '__main__':
    if len(args := sys.argv) > 2 and args[2].isdigit():
        limit = int(args[2])
    code = open(args[1]).read()

    while count < limit:
        inst = instruct % len(code)
        sym = code[inst]
        if sym == '>':
            pointer += 1
            if pointer > len(tape) - 1:
                tape.append(0)
        elif sym == '<':
            internal += tape[pointer]
            pointer = 0
        elif sym == '!':
            tape[pointer] = max(0, tape[pointer] + 1 - internal)
            pointer = internal = 0
        elif sym == ',':
            inp = input('\n' * line + 'Input: ')
            internal = internal + ord(inp[0]) if inp else 0
            line = 1
        elif sym == '.':
            print(chr(max(0, internal - 1)), end='')
        instruct += 1
        count = instruct // len(code)
