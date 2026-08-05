import math
import sys
from inspect import signature


def convert(func, num=None):
    if num is None:
        num = len(signature(func).parameters)
    total = 2 ** (num + 1) - 1
    lines = ["" for _ in range(total)]
    pos = [total // 2]

    for j in range(num + 1):
        if j < num:
            for k in range(total):
                if k in pos:
                    lines[k] += ">2$~;#@"
                else:
                    lines[k] += " " * 7
            pos = [i + 2 ** (num - j - 1) for i in pos] + [
                i - 2 ** (num - j - 1) for i in pos
            ]
            for k in pos:
                lines[k] = lines[k][:-2] + "> "
        else:
            for k in range(2**num):
                arg_list = [0] * num + [int(i) for i in bin(k)[2:]]
                lines[k * 2] += f">$3{func(*arg_list[-num:])}:@"

    lines[0] = "'" + lines[0][1:]
    return "\n".join(k for k in lines).replace("> >", ">  ")


def main() -> None:
    """Generate a Dig program for the boolean function given as a truth table."""
    if len(sys.argv) < 2:
        print("usage: python -m esolangs.tools.binary <truth table>")
        print("example: python -m esolangs.tools.binary 0111  # 2-input OR gate")
        sys.exit(1)

    table = sys.argv[1]
    num = round(math.log2(len(table)))
    if 2**num != len(table):
        print("error: truth table length must be a power of 2")
        sys.exit(1)

    bits = [int(c) for c in table]

    def fn(*args: bool) -> int:
        index = 0
        for arg in args:
            index = index * 2 + int(arg)
        return bits[index]

    print(convert(fn, num))


if __name__ == "__main__":
    main()
