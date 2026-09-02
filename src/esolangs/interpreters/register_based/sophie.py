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

The interpreter runs on a :class:`_Machine` (the code, accumulator, loop
stack, and skip flag), so it is step-capable: ``step()`` executes one
command and ``halted`` is true once ``&`` fires or the cursor reaches the
end of the code.
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


class _Machine:
    """Per-run Sophie state: the code, accumulator, loop stack, and cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Validate ``code``'s brackets and start with a zero accumulator.

        Unbalanced brackets are a malformed program, raised eagerly before
        any command runs.
        """
        matches(code)
        self.io = io
        self.code = code
        self.acc = self.ind = 0
        self.skp = False
        self.stk: list[int] = []
        self._halted_by_command = False

    @property
    def halted(self) -> bool:
        """Whether ``&`` fired or the cursor reached the end of the code."""
        return self._halted_by_command or self.ind >= len(self.code)

    # The VM's language-shaped view: Accumulator + loop stack; ip the cursor, memory
    # the acc.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.acc]

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.stk)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.acc,
            self.skp,
            tuple(self.stk),
            self._halted_by_command,
        )

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the cursor."""
        if self.halted:
            return
        code = self.code
        ind = self.ind
        if (c := code[ind]) == "[":
            if self.skp:
                ind = find(code, ind)
                if not self.stk:
                    self.skp = False
            else:
                self.stk.append(ind)
        elif c in "]*":
            if not self.stk:
                raise HaltError
            ind = self.stk.pop() - 1
            if c == "*":
                self.skp = True
        elif c == ".":
            self.io.print_num(self.acc)
        elif c == ":":
            num = self.io.input_str()
            if num.isdigit():
                self.acc = int(num)
        elif c == ",":
            self.io.print_char(chr(self.acc))
        elif c == ";":
            val = self.io.input_str()
            if val:
                self.acc = ord(val[0])
        elif c == "{":
            ind = find(code, ind)
        elif c == "&":
            self._halted_by_command = True
            return
        else:
            val = code[ind:]
            if m := re.match(r"@\$(\d+){", val):
                n = m.end() - 1
                if self.acc == int(m[1]):
                    ind += n
                else:
                    end = find(code, ind + n)
                    if end + 1 < len(code) and code[end + 1] == "{":
                        ind = end + 1
                    else:
                        ind = end
            elif m := re.match(r"@\$?(.){", val):
                n = m.end() - 1
                if self.acc == ord(m[1]):
                    ind += n
                else:
                    end = find(code, ind + n)
                    if end + 1 < len(code) and code[end + 1] == "{":
                        ind = end + 1
                    else:
                        ind = end
            elif m := re.match(r"#\$(\d+)", val):
                self.acc = int(m[1])
                ind += m.end() - 1
            elif m := re.match(r"#\$?(.)", val):
                self.acc = ord(m[1])
                ind += m.end() - 1

        self.ind = ind + 1


def run(code: str, io: IO) -> None:
    """Execute Sophie program code."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
