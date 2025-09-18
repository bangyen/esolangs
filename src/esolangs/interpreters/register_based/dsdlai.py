import secrets as s
import sys

import dig


def rand():
    num = s.randbelow(71) + 20

    def chance():
        n = s.randbelow(100) + 1
        if n <= num:
            print("\nYou died.")
        return n <= num

    return chance


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            dig.run(data, rand())
