"""Interpreter for Forþ.

A stack-based language with a dispatch table of named functions.  Digits
0-9 and A-F push their value, ``:`` duplicates the top, ``+``/``-``/``*``/
``/``/``%`` do arithmetic (the top goes on the right), ``~`` pushes the
bitwise complement of the top, ``.`` prints the top as a character, ``,``
reads a line pushing each byte (rightmost on top), ``(``/``[`` branch or
loop while the top is nonzero, ``{`` stores a scope under the number atop
the stack, ``;`` calls the stored scope, ``o`` reverses the stack, ``c``
rotates the top three, and ``v`` swaps the top two.  Any other character is
ignored.

Semantics match the Rust cross-check (``extra/rust/forth.rs``):
- arithmetic wraps to signed 32-bit integers, and ``/``/``%`` truncate
  toward zero (C++11 semantics), so negative operands match;
- an empty-stack pop halts the whole program with :class:`HaltError`, while
  the other invalid operations (a binary operator with fewer than two
  values, ``c`` with fewer than three, a division by zero, or an unterminated
  bracket) abort only the innermost scope and are otherwise ignored -- the
  cross-check returns an error code that nested calls discard;
- ``,`` reads a whole line and raises :class:`EOFError` when input runs out
  (like the other stack interpreters), where the cross-check exits with
  status 3;
- ``,`` pushes each character's byte value (the cross-check's signed ``char``
  would push negative values for bytes above 127);
- ``.`` prints the top's low byte (``& 0xFF``), matching the Rust cross-check,
  rather than the wiki's "print as a unicode character" -- the byte model is
  baked into the arithmetic (``~`` complements, so ``.`` on ``-1`` prints the
  byte 0xFF).
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def _wrap32(value: int) -> int:
    """Wrap ``value`` to a signed 32-bit integer (C++ ``int`` arithmetic)."""
    return (value + 2**31) % 2**32 - 2**31


def _trunc_div(a: int, b: int) -> int:
    """C++-style integer division, truncating toward zero."""
    return int(a / b)


def _trunc_mod(a: int, b: int) -> int:
    """C++-style remainder (the sign of the dividend)."""
    return a - _trunc_div(a, b) * b


def _execute(code: str, stack: list[int], table: dict[int, str], io: IO) -> int:
    """Run ``code`` on ``stack``/``table``, returning the cross-check status.

    The status is 3 (invalid operation) when a scope aborts on an error; the
    callers of ``;`` and ``(``/``[`` discard it, mirroring the cross-check,
    while an empty-stack pop raises :class:`HaltError` instead, mirroring its
    ``exit()`` which terminates the whole program.
    """

    def top() -> int:
        if not stack:
            raise HaltError
        return stack[-1]

    def pop() -> int:
        value = top()
        stack.pop()
        return value

    k = 0
    n = len(code)
    while k < n:
        char = code[k]
        k += 1
        if "0" <= char <= "9":
            stack.append(ord(char) - 48)
        elif "A" <= char <= "F":
            stack.append(ord(char) - 55)
        elif char == ":":
            stack.append(top())
        elif char == "~":
            stack.append(~pop())
        elif char == ".":
            io.print_char(chr(pop() & 0xFF))
        elif char == ",":
            for ch in io.input_str("Input: "):
                stack.append(ord(ch) & 0xFF)
        elif char == ";":
            scope = table.get(pop(), "")
            _execute(scope, stack, table, io)
        elif char == "o":
            stack.reverse()
        elif char == "c":
            if len(stack) < 3:
                return 3
            stack.append(stack.pop(-3))
        elif char in "([{":
            add = char
            sub = ")" if char == "(" else "]" if char == "[" else "}"
            start = k - 1
            match = 1
            while True:
                if k >= n:
                    return 3  # unterminated bracket
                inner = code[k]
                k += 1
                if inner == add:
                    match += 1
                elif inner == sub:
                    match -= 1
                if match == 0:
                    break
            scope = code[start + 1 : k - 1]
            if add == "(":
                if top():
                    _execute(scope, stack, table, io)
            elif add == "[":
                while top():
                    _execute(scope, stack, table, io)
            else:
                table[top()] = scope
        elif char in "+-*/%v":
            if len(stack) < 2:
                return 3
            two = pop()
            one = pop()
            if char == "+":
                stack.append(_wrap32(one + two))
            elif char == "-":
                stack.append(_wrap32(one - two))
            elif char == "*":
                stack.append(_wrap32(one * two))
            elif char == "/":
                if two == 0:
                    return 3
                stack.append(_wrap32(_trunc_div(one, two)))
            elif char == "%":
                if two == 0:
                    return 3
                stack.append(_wrap32(_trunc_mod(one, two)))
            elif char == "v":
                stack.append(two)
                stack.append(one)
    return 0


def run(code: str, io: IO) -> None:
    """Run a Forþ program."""
    if _execute(code, [], {}, io):
        raise HaltError


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
