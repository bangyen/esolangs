"""Sophie interpreter implementation.

Esoteric language equivalent to a Finite State Automaton.
Single accumulator with basic control flow operations.

`*` breaks out of the whole enclosing loop nest (and later loops run
normally); a single-branch `@c{}` skips its block cleanly when the condition
fails.  `&` halts.  Unbalanced brackets are a malformed program and are
rejected with :class:`ValueError`; a `*` break with no enclosing loop is an
invalid operation and halts the program with
:class:`~esolangs.exceptions.HaltError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import re
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def matches(code: str) -> None:
    """Raise :class:`ValueError` if ``[]`` or ``{}`` brackets are unbalanced.

    The wiki defines ``[``/``]`` loops and ``{``/``}`` blocks (conditionals
    and comments) only for matched pairs; a program with unbalanced brackets
    is malformed, so the interpreter rejects it rather than inventing a halt.
    A ``#`` load consumes one data character (``#$`` an optional marker plus
    digits or a character), so a bracket loaded that way is data, not
    structure.
    """
    for opr, end in (("[", "]"), ("{", "}")):
        depth = 0
        i = 0
        while i < len(code):
            char = code[i]
            if char == "#":
                i += 1
                if i < len(code) and code[i] == "$":
                    i += 1
                    if i < len(code) and code[i].isdigit():
                        while i < len(code) and code[i].isdigit():
                            i += 1
                    elif i < len(code):
                        i += 1  # #$<char>: the optional marker plus one char
                elif i < len(code):
                    i += 1  # the loaded character
                continue
            if char == opr:
                depth += 1
            elif char == end:
                if depth == 0:
                    raise ValueError(f"unmatched '{end}' at position {i}")
                depth -= 1
            i += 1
        if depth:
            raise ValueError(f"unmatched '{opr}'")


def find(code: str, ind: int) -> int:
    """Find the matching closing bracket for a given opening bracket."""
    opr = code[ind]
    end = chr(ord(opr) + 2)
    match = 1

    while match:
        ind += 1
        if ind == len(code):
            break
        if (c := code[ind]) == opr:
            match += 1
        elif c == end:
            match -= 1
    return ind


def run(code: str, io: IO) -> None:
    """Execute Sophie program code."""
    matches(code)
    acc = ind = 0
    skp = False
    stk: list[int] = []

    while ind < len(code):
        if (c := code[ind]) == "[":
            if skp:
                ind = find(code, ind)
                if not stk:
                    skp = False
            else:
                stk.append(ind)
        elif c in "]*":
            if not stk:
                raise HaltError
            ind = stk.pop() - 1
            if c == "*":
                skp = True
        elif c == ".":
            io.print_num(acc)
        elif c == ":":
            num = io.input_str()
            if num.isdigit():
                acc = int(num)
        elif c == ",":
            io.print_char(chr(acc))
        elif c == ";":
            val = io.input_str()
            if val:
                acc = ord(val[0])
        elif c == "{":
            ind = find(code, ind)
        elif c == "&":
            return
        else:
            val = code[ind:]
            if m := re.match(r"@\$(\d+){", val):
                n = m.end() - 1
                if acc == int(m[1]):
                    ind += n
                else:
                    end = find(code, ind + n)
                    if end + 1 < len(code) and code[end + 1] == "{":
                        ind = end + 1
                    else:
                        ind = end
            elif m := re.match(r"@\$?(.){", val):
                n = m.end() - 1
                if acc == ord(m[1]):
                    ind += n
                else:
                    end = find(code, ind + n)
                    if end + 1 < len(code) and code[end + 1] == "{":
                        ind = end + 1
                    else:
                        ind = end
            elif m := re.match(r"#\$(\d+)", val):
                acc = int(m[1])
                ind += m.end() - 1
            elif m := re.match(r"#\$?(.)", val):
                acc = ord(m[1])
                ind += m.end() - 1

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
