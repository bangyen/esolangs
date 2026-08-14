"""Interpreter for Collatz Multiverse.

An OISC where every line is ``[var1] = [var2] x + [var3], [DO|NOT] PRINT.``
The Collatz rule applies to var1: if it is odd (or 0), it becomes
``var1 * var2 + var3``; if it is even, it is halved.  ``DO`` prints the
result as a byte, ``NOT`` does not.  Variables are named by letters, digits,
and underscores (not starting with a digit) and start at 0; ``arr[var]``
indexes an array (bare ``arr`` acts as ``arr[0]``); ``negativeOne`` starts
at -1; ``input`` reads an integer from stdin and cannot be a target; and
``lineNumber`` reads the current line (1-indexed), and assigning to it moves
the instruction pointer to that line without executing it immediately.

Documented decisions for gaps in the wiki spec:
- the program is its non-blank lines, numbered from 1; execution starts at
  line 1 and halts when the pointer leaves the program;
- var2/var3 and array indices must be variable names, not numeric literals
  (the wiki rejects ``var = 3 x + 1``);
- assigning to ``lineNumber`` applies the Collatz rule to the current line
  number and jumps to the result (the wiki does not exempt it);
- ``DO`` prints the low byte of the result;
- ``input`` raises :class:`EOFError` when input runs out (repo-wide
  convention);
- a malformed line, a numeric literal, or an attempt to redefine ``input``
  is malformed (:class:`ValueError`).
"""

import re
import sys

from esolangs.interpreters.io import IO

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_LINE = re.compile(
    rf"^\s*({_NAME})(?:\[({_NAME})\])?\s*=\s*"
    rf"({_NAME})(?:\[({_NAME})\])?\s*x\s*\+\s*"
    rf"({_NAME})(?:\[({_NAME})\])?\s*,\s*(DO|NOT)\s+PRINT\.\s*$"
)


def run(code: str, io: IO) -> None:
    """Run a Collatz Multiverse program."""
    lines = [ln for ln in code.splitlines() if ln.strip()]
    n = len(lines)
    parsed = []
    for ln in lines:
        m = _LINE.fullmatch(ln)
        if not m:
            raise ValueError(f"malformed line: {ln!r}")
        parsed.append(m.groups())

    registers: dict[str, int] = {"negativeOne": -1}
    arrays: dict[str, dict[int, int]] = {}
    ip = 1

    def read(spec: tuple[str, str | None]) -> int:
        name, index = spec
        if name == "input":
            return io.input_num("Input: ")
        if name == "lineNumber":
            return ip
        if index is not None:
            return arrays.setdefault(name, {}).get(read((index, None)), 0)
        return registers.get(name, 0)

    while 1 <= ip <= n:
        var1, idx1, var2, idx2, var3, idx3, do_print = parsed[ip - 1]
        if var1 == "input":
            raise ValueError("input cannot be redefined")

        t = read((var1, idx1))
        a = read((var2, idx2))
        b = read((var3, idx3))
        t = t * a + b if t == 0 or t % 2 != 0 else t // 2

        next_ip = ip + 1
        if var1 == "lineNumber":
            next_ip = t
        elif idx1 is not None:
            arrays.setdefault(var1, {})[read((idx1, None))] = t
        else:
            registers[var1] = t

        if do_print == "DO":
            io.print_char(chr(t & 0xFF))
        ip = next_ip


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
