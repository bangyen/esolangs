import secrets
import sys
import time


def run(code):
    bit = ind = 0
    vel = new = 1

    while ind < len(code):
        sym = code[ind]
        if sym == "^":
            bit ^= 1
        elif sym == "!":
            print(bit, end="")
            new = 0
        elif sym == "?":
            val = input("\nInput: "[new:])
            bit = (not val) + 0
            new = 1
        elif sym == "@":
            bit = secrets.randbelow(2)
        elif sym == "&" and bit:
            ind += vel
        elif sym == "#":
            return
        elif sym == "<":
            ind = -vel
        elif sym == "/":
            vel *= -1
        elif sym == "_":
            time.sleep(1)

        ind += vel


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
