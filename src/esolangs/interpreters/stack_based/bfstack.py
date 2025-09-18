import sys


def run(code):
    stk = []
    lst = []
    new = 1
    ind = 0

    while ind < len(code):
        if (char := code[ind]) == ">":
            stk.append(0)
        elif char == "<":
            stk.pop()
        elif char == "+":
            stk[-1] = (stk[-1] + 1) % 256
        elif char == "-":
            stk[-1] = (stk[-1] - 1) % 256
        elif char == ".":
            print(chr(stk[-1]), end="")
            new = 0
        elif char == ",":
            val = input("\nInput: "[new:])
            stk.append(ord(val[0]))
            new = 1
        elif char == "[":
            if stk[-1]:
                lst.append(ind)
            else:
                match = 1
                while match:
                    ind += 1
                    if ind == len(code):
                        break
                    elif (o := code[ind]) == "[":
                        match += 1
                    elif o == "]":
                        match -= 1
        elif char == "]":
            ind = lst.pop() - 1

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
