import re
import sys


def run(code):
    reg = re.compile(r"(\d+) *= *(\d+)")
    arr = dict.fromkeys(range(5), 0)
    num = ind = 0
    new = 1

    for m in reg.finditer(code[0]):
        x, y = m[1], m[2]
        if x == "42":
            x = input("Key: ")
        elif y == "42":
            y = input("Value: ")
            y = y if y else 0
        arr[int(x)] = int(y)

    code = code[1:]
    while num < 2:
        copy = arr.copy()
        expr = r"(move *(-?\d+)" r" *(-?\d+)|sum)"

        match_result = re.search(expr, code[ind])
        if match_result:
            if match_result[1] == "sum":
                arr[0] = arr[1]
                for k in range(2, 5):
                    arr[0] += arr[k]
            else:
                if match_result[2].isdigit():
                    x = int(match_result[2])
                    n = arr.get(x, 0)

                    if match_result[3].isdigit():
                        y = int(match_result[3])
                        arr[y] = n
                    else:
                        print(n, end=" ")
                        new = 0
                elif match_result[3].isdigit():
                    y = int(match_result[3])
                    input_str: str = input("\nInput: "[new:])
                    arr[y] = int(input_str) if input_str else 0
                    new = 1

        num = (num + 1) * (arr == copy)
        ind = (ind + 1) % len(code)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
