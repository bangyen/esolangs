r"""Sophie interpreter implementation."""

import re
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def matches(code: str) -> None:
    r"""Raise :class:`ValueError` if ``[]`` or ``{}`` brackets are."""
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
                        i += 1  # #$<char>: the optional marker.
                elif i < len(code):
                    i += 1  # the loaded character.
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
    r"""Find the matching closing bracket for a given opening bracket."""
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


# : One instant of a run:.
# : accumulator, the cursor,.
# : positions, and whether.
# : forward, with the stack as.
# :.
# : ``skp`` is state, not a.
# : *later* ``[`` reads it to.
# : it, so the flag outlives.
# : makes a break escape a.
# :.
# : The code is not here:.
# : the program rather than.
type _State = tuple[int, int, bool, tuple[int, ...], bool]


def _advance(state: _State, code: str, value: int | None = None) -> _State:
    r"""Return the state after executing the command under the cursor."""
    acc, ind, skp, stk, halted = state

    if (c := code[ind]) == "[":
        if skp:
            ind = find(code, ind)
            if not stk:
                skp = False
        else:
            stk = (*stk, ind)
    elif c in "]*":
        if not stk:
            raise HaltError(f"{c!r} at position {ind} closes a loop that never opened")
        ind = stk[-1] - 1
        stk = stk[:-1]
        if c == "*":
            skp = True
    elif c in ".,":
        pass  # printed by the caller; the.
    elif c in ":;":
        if value is not None:
            acc = value
    elif c == "{":
        ind = find(code, ind)
    elif c == "&":
        return (acc, ind, skp, stk, True)
    else:
        val = code[ind:]
        if m := re.match(r"@\$(\d+){", val):
            ind = _branch(code, ind, m.end() - 1, taken=acc == int(m[1]))
        elif m := re.match(r"@\$?(.){", val):
            ind = _branch(code, ind, m.end() - 1, taken=acc == ord(m[1]))
        elif m := re.match(r"#\$(\d+)", val):
            acc = int(m[1])
            ind += m.end() - 1
        elif m := re.match(r"#\$?(.)", val):
            acc = ord(m[1])
            ind += m.end() - 1

    return (acc, ind + 1, skp, stk, halted)


def _branch(code: str, ind: int, width: int, *, taken: bool) -> int:
    r"""Return the cursor for a conditional, entered or skipped."""
    if taken:
        return ind + width
    end = find(code, ind + width)
    if end + 1 < len(code) and code[end + 1] == "{":
        return end + 1
    return end


class _Machine:
    r"""Per-run Sophie state: the code, accumulator, loop stack, and cursor."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Validate ``code``'s brackets and start with a zero accumulator."""
        matches(code)
        self.io = io
        self.code = code
        self.acc = self.ind = 0
        self.skp = False
        self.stk: tuple[int, ...] = ()
        self._halted_by_command = False

    @property
    def halted(self) -> bool:
        r"""Whether ``&`` fired or the cursor reached the end of the code."""
        return self._halted_by_command or self.ind >= len(self.code)

    # The VM's language-shaped.
    # the acc.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [self.acc]

    @property
    def stack(self) -> list[object]:
        r"""The stack."""
        return list(self.stk)

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.acc,
            self.skp,
            self.stk,
            self._halted_by_command,
        )

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transition works on."""
        return (self.acc, self.ind, self.skp, self.stk, self._halted_by_command)

    def _restore(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        self.acc, self.ind, self.skp, self.stk, self._halted_by_command = state

    def step(self) -> None:
        r"""Execute one command, advancing (or jumping) the cursor."""
        if self.halted:
            return
        c = self.code[self.ind]

        value: int | None = None
        if c == ".":
            self.io.print_num(self.acc)
        elif c == ",":
            self.io.print_char(chr(self.acc))
        elif c == ":":
            num = self.io.input_str()
            if num.isdigit():
                value = int(num)
        elif c == ";":
            val = self.io.input_str()
            if val:
                value = ord(val[0])

        self._restore(_advance(self._state, self.code, value))


def run(code: str, io: IO) -> None:
    r"""Execute Sophie program code."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
