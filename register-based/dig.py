import sys


def run(code, func=lambda: 0):
    size = max(len(lne) for lne in code)
    code = [c.ljust(size) for c in code]

    direct = [(-1, 0), (0, 1), (1, 0), (0, -1)]
    line = mole = num = x = y = 0
    move = 1

    def value():
        lst = []
        for i, j in direct:
            if 0 <= x + i < len(code) and 0 <= y + j < size:
                val = code[x + i][y + j]
                if val.isdigit():
                    lst.append(int(val))
        return lst[0]

    while True:
        char = code[x][y]
        if num:
            if char == "%":
                if (n := value()) == 1:
                    mole = 10
                elif n == 0:
                    mole = 32
            elif char in "=~":
                temp = input("\n" * line + "Input: ")
                line = False

                if char == "=":
                    mole = ord(temp[0])
                else:
                    mole = int(temp[0])
            elif char == ":":
                if mole < 10:
                    print(mole, end="")
                else:
                    print(chr(mole), end="")

                line = True
                mole = 0
            elif char == "+":
                mole += value()
            elif char == "-":
                mole -= value()
            elif char == "*":
                mole += value()
            elif char == "/":
                mole //= value()
            elif char == ";":
                code[x] = code[x][:y] + str(mole) + code[x][y + 1 :]
            elif char.isdigit():
                mole = int(char)
            elif char.isalpha() or char in ".,!?":
                mole = ord(char)
            num -= 1
        else:
            if char in "^>'<":
                move = "^>'<".find(char)
            elif char == "#":
                if (n := value()) == 1:
                    move += 1
                elif n == 0:
                    move -= 1
                move %= 4
            elif char == "$":
                if func():
                    break
                num = value()
            elif char == "@":
                break

        x += direct[move][0]
        y += direct[move][1]


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
