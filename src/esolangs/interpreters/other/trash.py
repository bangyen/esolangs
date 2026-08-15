r"""Interpreter for Trash.

The program is a number: the leading ``t`` characters count how many prime
steps to take, and the remaining characters hold the starting value.  If the
starting value is prime, the program prints the value advanced by that many
primes; otherwise it prints 0.  A program with no digits is malformed.

The language has no input command; the program file itself is the source.

Semantics follow the Rust cross-check (``extra/rust/trash.rs``, itself a
port of the original C++ reference) exactly:

* only ``t`` characters before the first digit contribute to the step count,
  and other characters there are ignored;
* only the leading digits after the first digit form the starting value, so
  trailing characters do not affect the result;
* the primality test is trial division up to the square root, which treats 2
  as prime, so a starting value of 2 advances rather than printing 0.
"""

import re
import sys
from math import isqrt

from esolangs.interpreters.io import IO


def _prime(n: int) -> bool:
    """Return whether ``n`` is prime (2 is prime, per the wiki)."""
    if n < 2:
        return False
    return all(n % k != 0 for k in range(2, isqrt(n) + 1))


def run(code: str, io: IO) -> None:
    """Run a Trash program, printing the advanced prime or 0."""
    match = re.search(r"[0-9]+", code)
    if match is None:
        raise ValueError("Trash program must contain at least one digit")

    num = code.count("t", 0, match.start())
    val = int(match.group(0))

    if num:
        if _prime(val):
            for _ in range(num):
                val += 1
                while not _prime(val):
                    val += 1
            io.print_num(val)
        else:
            io.print_num(0)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
