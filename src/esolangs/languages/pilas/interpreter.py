"""Interpreter for Pilas.

A program is two lines, each driving its own stack with its own
instruction pointer.  The lines take turns: line one runs a command, then
line two, then line one again.  The run halts as soon as either pointer
passes the end of its line.

Commands:
    ``0``-``9``  push the digit
    ``+``        pop a, then b; push b + a
    ``-``        pop a, then b; push b - a
    ``:``        duplicate the top
    ``~``        pop a value and push it onto the other line's stack
    ``{``        pop; nonzero jumps past the matching ``}`` (same line)
    ``}``        jump back to the matching ``{``, which pops again
    ``,``        push the next input byte
    ``.``        pop and print the value as a character
    other        a no-op that still takes its turn

Input/output:
    ``,`` reads one byte and ``.`` writes one character.

Errors:
    ProgramError: more than two lines, or an unmatched brace.
    InputExhaustedError: ``,`` at EOF.
    HaltError: a pop from an empty stack, or ``.`` of a value outside
    Unicode.

Decisions:
    * ``}`` jumps unconditionally to its ``{``, so the pop "at each
      iteration" happens at ``{`` only; the page's while-zero translation
      ``:~:{ ... :~:}`` balances either way.
    * A step is one line's command, not a pair, so the halt check between
      the two halves of a turn sees line one run off before line two runs.
    * A one-line program has an empty second line and halts at once; the
      page requires two lines but gives no error for one.
    * Values are unbounded signed integers; the page leaves the sign open.
    * An empty-stack pop halts with an error: the page gives no default.
"""

from __future__ import annotations

from typing import NamedTuple

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: Commands that pop, with how many values each needs.
_POPS = {"+": 2, "-": 2, ":": 1, "~": 1, "{": 1, ".": 1}


class _State(NamedTuple):
    """The two pointers, the two stacks, and whose turn it is."""

    ips: tuple[int, int]
    stks: tuple[tuple[int, ...], tuple[int, ...]]
    turn: int


def _braces(line: str) -> dict[int, int]:
    """Map each brace to its partner, both ways, rejecting a stray one."""
    table: dict[int, int] = {}
    open_: list[int] = []
    for ind, char in enumerate(line):
        if char == "{":
            open_.append(ind)
        elif char == "}":
            if not open_:
                raise syntax_error("unmatched '}'", "open the loop with {")
            start = open_.pop()
            table[start], table[ind] = ind, start
    if open_:
        raise syntax_error("unmatched '{'", "close the loop with }")
    return table


def _advance(
    state: _State,
    lines: tuple[str, str],
    jumps: tuple[dict[int, int], dict[int, int]],
    byte: int | None = None,
) -> tuple[_State, str | None]:
    """Return the state after the current line's command, and its output.

    Pure; the shell has already checked the stack depth and read ``byte``.
    """
    ips, stks, me = state
    ip, stk, other = ips[me], stks[me], stks[1 - me]
    char = lines[me][ip]
    out = None
    if char.isdigit() and char.isascii():
        stk = (*stk, int(char))
    elif char == "+":
        stk = (*stk[:-2], stk[-2] + stk[-1])
    elif char == "-":
        stk = (*stk[:-2], stk[-2] - stk[-1])
    elif char == ":":
        stk = (*stk, stk[-1])
    elif char == "~":
        stk, other = stk[:-1], (*other, stk[-1])
    elif char == "{":
        if stk[-1]:
            ip = jumps[me][ip]
        stk = stk[:-1]
    elif char == "}":
        ip = jumps[me][ip] - 1
    elif char == "," and byte is not None:
        stk = (*stk, byte)
    elif char == ".":
        out, stk = chr(stk[-1]), stk[:-1]
    new_ips = (ip + 1, ips[1]) if me == 0 else (ips[0], ip + 1)
    new_stks = (stk, other) if me == 0 else (other, stk)
    return _State(new_ips, new_stks, 1 - me), out


class _Machine:
    """A Pilas run: both lines, rebound to a new ``_State`` per step."""

    # ``ip`` is one pointer per line, not a single place in the source.
    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        lines = code.split("\n")
        if len(lines) > 2:
            raise syntax_error(
                f"{len(lines)} lines; Pilas programs have two",
                "join the extra lines into the two stack lines",
            )
        first, second = (*lines, "")[:2]
        self.lines = (first, second)
        self.jumps = (_braces(first), _braces(second))
        self.io = io
        self.state = _State((0, 0), ((), ()), 0)

    @property
    def ip(self) -> tuple[int, int]:
        return self.state.ips

    @property
    def halted(self) -> bool:
        """Whether either pointer has passed the end of its line."""
        return any(
            ip >= len(line) for ip, line in zip(self.state.ips, self.lines, strict=True)
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Run the current line's command; reads and writes happen here."""
        if self.halted:
            return
        ips, stks, me = self.state
        char = self.lines[me][ips[me]]
        if len(stks[me]) < _POPS.get(char, 0):
            raise HaltError(
                f"{char!r} on line {me + 1} at column {ips[me]} needs "
                f"{_POPS[char]} value(s) and the stack holds {len(stks[me])}",
                hint="push enough values before popping",
            )
        if char == "." and not 0 <= stks[me][-1] <= 0x10FFFF:
            raise HaltError(
                f"'.' cannot print {stks[me][-1]} as a character",
                hint="keep printed values between 0 and 0x10FFFF",
            )
        byte = self.io.input_char() if char == "," else None
        self.state, out = _advance(self.state, self.lines, self.jumps, byte)
        if out is not None:
            self.io.print_char(out)


def run(code: str, io: IO) -> None:
    """Run a Pilas program until either line's pointer runs off its end."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
