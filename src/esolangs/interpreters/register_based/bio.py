import re
import sys


def run(code):
    lang = "([01][oOiI][xyz]|})"
    code = re.findall(lang, code)
    code = [k.lower() for k in code]

    reg = [0] * 3
    stk: list = []
    ind = 0

    while ind < len(code):
        r = "xyz".find(code[ind][-1])
        c = code[ind][:2]

        if c == "0o":
            reg[r] += 1
        elif c == "1o":
            reg[r] -= 1
        elif c == "1i":
            print(chr(reg[r]), end="")
        elif c == "}":
            ind = stk.pop() - 1
        else:
            if reg[r]:
                stk.append(ind)
            else:
                mat = 1
                while mat:
                    ind += 1
                    if ind == len(code):
                        break
                    else:
                        c = code[ind][:2]
                        if c == "0i":
                            mat += 1
                        elif c == "}":
                            mat -= 1
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
