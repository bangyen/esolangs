"""
Movesum interpreter implementation.

Movesum is an esoteric programming language by User:PythonshellDebugwindow where
the only instructions are 'move' and 'sum'. Programs operate on a right-unbounded
array of unbounded unsigned integers with 0-based indexing.

The language features:
- Initial array setup via key=value pairs on the first line
- Special value 42 for user input (replaced with 0 on EOF)
- Move instruction: copies values between array positions or handles I/O
- Sum instruction: sets position 0 to sum of positions 1-4
- Automatic halting when array doesn't change after two commands
"""

import re
import sys
from typing import Dict, List


def run(code: List[str]) -> None:
    """Execute a Movesum program with move and sum instructions."""
    if not code:
        raise ValueError("Movesum program cannot be empty")

    if len(code) < 2:
        raise ValueError(
            "Movesum program must have at least initialization and one instruction"
        )
    reg: re.Pattern[str] = re.compile(r"(\d+) *= *(\d+)")
    arr: Dict[int, int] = dict.fromkeys(range(5), 0)
    num: int = 0
    ind: int = 0
    new: int = 1

    for m in reg.finditer(code[0]):
        x: str = m[1]
        y: str = m[2]
        if x == "42":
            x = input("Key: ")
        elif y == "42":
            y = input("Value: ")
            y = y if y else "0"
        arr[int(x)] = int(y)

    code = code[1:]
    while num < 2:
        copy: Dict[int, int] = arr.copy()
        expr: str = r"(move *(-?\d+)" r" *(-?\d+)|sum)"

        match_result = re.search(expr, code[ind])
        if match_result:
            if match_result[1] == "sum":
                arr[0] = arr[1]
                for k in range(2, 5):
                    arr[0] += arr[k]
            else:
                if match_result[2].isdigit():
                    src_idx: int = int(match_result[2])
                    n: int = arr.get(src_idx, 0)

                    if match_result[3].isdigit():
                        dst_idx: int = int(match_result[3])
                        arr[dst_idx] = n
                    else:
                        print(n, end=" ")
                        new = 0
                elif match_result[3].isdigit():
                    input_dst_idx: int = int(match_result[3])
                    input_str: str = input("\nInput: "[new:])
                    arr[input_dst_idx] = int(input_str) if input_str else 0
                    new = 1

        num = (num + 1) * (arr == copy)
        ind = (ind + 1) % len(code)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
