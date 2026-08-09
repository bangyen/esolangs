"""Polynomial interpreter implementation.

Polynomial is an esoteric programming language by User:Maedhros777 where each program
is a polynomial function. Language statements are executed based on the zeroes of the
function, with both real and complex zeroes allowed. The language operates on a single
integer register with operations determined by the mathematical properties of the roots.

The language features:
- Programs as polynomial functions in the form f(x) = ...
- Real zeroes for control flow (if/while statements)
- Complex zeroes for register operations (arithmetic, I/O)
- Special encoding using ascending primes for execution order
- Single integer register for all operations
"""

import re
import sys
from typing import Any

import numpy as np

from esolangs.interpreters.io import IO


def prime(number: int) -> bool:
    """Check if a number is prime."""
    if number < 2:
        return False
    return all(number % val for val in range(2, int(np.sqrt(number)) + 1))


def brackets(string: list[list[int]], pointer: int) -> int:
    """Find matching bracket for control flow statements."""
    length = len(string[pointer]) == 1
    end = string[pointer][0] in [2, 6]
    direct = (1, -1)[length and end]
    count = direct
    while count:
        pointer += direct
        if pointer < 0 or pointer >= len(string):
            return max(0, min(pointer, len(string) - 1))
        if len(string[pointer]) == 1:
            if string[pointer][0] in [2, 6]:
                count -= 1
            else:
                count += 1
    return pointer


def convert(pre: list[complex]) -> list[list[int]]:
    """Convert polynomial roots to instruction codes using prime encoding."""
    rounded_roots = [np.round(k) for k in pre]
    # Sort by imaginary part, then by real part
    sorted_roots = sorted(
        rounded_roots,
        key=lambda x: (float(np.imag(x)), float(np.real(x))),
    )
    post: list[list[int]] = []
    num = 2

    # A prime power p**v (v >= 1) is always >= p, so once num exceeds the
    # largest root magnitude no further root can match.
    if rounded_roots:
        limit = max(max(abs(np.imag(k)), abs(np.real(k))) for k in rounded_roots)
    else:
        limit = 0

    while sorted_roots and num <= limit + 1:
        if not prime(num):
            num += 1
            continue
        for root in sorted_roots[:]:  # Use slice to avoid modification during iteration
            if im := np.imag(root):
                for val in range(1, 7):
                    if im == num**val:
                        sorted_roots.remove(root)
                        post.append([int(np.real(root)), val])
                        break
            else:
                for val in range(1, 9):
                    if root == num**val:
                        sorted_roots.remove(root)
                        post.append([val])
                        break
        num += 1
    return post


def sanitize(code: str) -> list[int]:
    """Parse polynomial string into coefficient list."""
    # Remove "f(x) = " prefix (with or without surrounding spaces)
    match = re.match(r"f\(x\)\s*=\s*(.*)", code)
    if not match:
        return [0]

    code = match.group(1).strip()

    # Handle simple cases
    if not code or code == "0":
        return [0]

    # Normalize the polynomial string
    code = code.replace(" ", "")

    # Add explicit coefficients and degrees for x terms
    code = re.sub(r"(?<!\d)x(?!\^)", "1x^1", code)  # x -> 1x^1
    code = re.sub(r"x([+-])", r"x^1\1", code)  # x+ -> x^1+

    # Find all terms with their degrees and coefficients
    terms = {}

    # Find x^n terms first
    for match in re.finditer(r"(-?\d*)x\^(\d+)", code):
        coeff_str = match.group(1)
        if not coeff_str:
            coeff = 1
        elif coeff_str == "-":
            coeff = -1
        else:
            coeff = int(coeff_str)
        degree = int(match.group(2))
        terms[degree] = coeff

    # Remove x terms from code to find constants
    code_without_x = re.sub(r"-?\d*x\^\d+", "", code)

    # Find constant terms (remaining numbers)
    for match in re.finditer(r"-?\d+", code_without_x):
        coeff = int(match.group(0))
        terms[0] = coeff

    # If no terms found, return [0]
    if not terms:
        return [0]

    # Build coefficient list from highest to lowest degree
    max_degree = max(terms.keys())
    return [terms.get(degree, 0) for degree in range(max_degree, -1, -1)]


def run(code: str, io: IO) -> None:
    """Execute a Polynomial program by finding and processing its zeroes."""
    # Clean the input code
    cleaned_code = re.sub(r"[^\df(x)=+-^]", "", code)
    if cleaned_code[:5] != "f(x)=":
        raise ValueError("Polynomial program must start with 'f(x) = '")

    # Parse polynomial and get coefficients
    coefficients = sanitize(cleaned_code)

    # Find roots and filter for non-negative imaginary parts
    roots = [k for k in np.roots(coefficients) if np.imag(k) >= 0]

    # Convert roots to instruction codes
    instructions = convert(roots)

    ind = reg = 0
    # Use Any to avoid complex type checking issues with mixed lambda types
    sym: list[Any] = [
        lambda r, a: r + a,  # +=
        lambda r, a: r - a,  # -=
        lambda r, a: r * a,  # *=
        lambda r, a: r / a,  # /=
        lambda r, a: r % a,  # %=
        lambda r, a: r**a,  # ^
        lambda: reg > 0,  # if > 0
        0,  # endif
        lambda: reg < 0,  # if < 0
        lambda: not reg,  # if == 0
    ]

    # Safety counter to prevent infinite loops
    max_steps = 10000
    step_count = 0

    while ind < len(instructions) and step_count < max_steps:
        instruction = instructions[ind]
        one = instruction[0]
        rest = instruction[1:] if len(instruction) > 1 else []

        if two := ([*rest, 0])[0]:
            if one:
                reg = sym[two - 1](reg, one)
            elif two - 1:
                val = io.input_str() + chr(0)
                reg = ord(val[0]) or -1
            else:
                io.print_char(chr(max(0, reg)))
        elif one in [2, 6]:
            beg = instructions[brackets(instructions, ind)][0]
            if beg > 4 and sym[(beg - 1) % 4 + 6]():
                ind = brackets(instructions, ind)
        elif not sym[((one - 1) % 4) + 6]():
            ind = brackets(instructions, ind)
        ind += 1
        step_count += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
