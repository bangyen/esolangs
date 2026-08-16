r"""Interpreter for The Temporary Stack.

A single stack with two output modes (numeric/byte).  @ reads a line of input
as byte codes, v pushes an integer, * pushes a string, + duplicates, : loops
while the stack is unchanged, \\ loops while it is nonempty, and a draining
loop prints values while the average of the tail exceeds the head.

As the wiki specifies, every fifteen commands (including comments) the stack
is reset, hence the name "The The Temporary Stack Stack".  Duplicating an empty stack,
or squishing a value that is not a valid character in byte mode, is an invalid
operation and halts the program with
:class:`~esolangs.exceptions.HaltError`; a word carrying more than one
distinct command (``o@\@``), or a ``:`` with no instruction after it, is a
malformed program rejected with :class:`ValueError`.


Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import re
import secrets
import sys
from dataclasses import dataclass, field

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The command characters; every other character is a comment.  A word's
# command is its first command character, and a word may only carry one
# distinct command, so comments may appear inside a command (``cOOde`` is
# ``O`` and ``hv1no2th3ing`` pushes 123) but ``o@\@`` is an invalid command.
_COMMANDS = r"[@v*oO+:\#€\\]"


@dataclass
class State:
    """Stack, output mode, and counters for a The Temporary Stack run."""

    stk: list[int] = field(default_factory=list)
    num: bool = True
    ptr: int = 0
    comm: int = 0
    code: list[str] = field(default_factory=list, init=False)
    io: IO = field(default_factory=IO)

    @property
    def halted(self) -> bool:
        """Whether the word pointer has run off the program."""
        return self.ptr >= len(self.code)

    def execute(self, char: str, rest: str) -> None:
        """Run the single-command words (the non-recursive commands)."""
        if char == "@":
            s = self.io.input_str()
            self.stk.extend(ord(c) for c in s)
        elif char == "v":
            self.stk.append(int(re.sub(r"\D", "", rest)))
        elif char == "*":
            self.stk.extend(ord(c) for c in rest)
        elif char in "oO":
            self.num = char == "O"
        elif char == "+":
            if not self.stk:
                raise HaltError
            self.stk.append(self.stk[-1])
        elif char == "€":
            self.execute(secrets.choice("@v*oO+"), rest)
        # ':', '\\', and '#' fall through: ':'/'\\' are handled in parse
        # because they recurse over the source, and '#' is a no-op comment

    def parse(self) -> None:
        r"""Execute one word, including the recursive ``:``/``\`` loops."""
        word = self.code[self.ptr]
        m = re.search(_COMMANDS, word)
        if m:
            char = m.group(0)
            rest = word[m.end() :]
            if char not in "v*€" and set(re.findall(_COMMANDS, word)) - {char}:
                # only one command per word, per the author's talk-page
                # clarification (``o@\@`` is invalid); ``cOOde`` is still
                # ``O`` because the repeated O is the same command
                raise ValueError(f"multiple commands in one word: {word!r}")
        else:
            char = ""
            rest = ""

        if char == ":":
            self.ptr += 1
            if self.ptr >= len(self.code):
                raise ValueError("':' requires a following instruction")
            n = len(self.stk)
            while len(self.stk) == n:
                self.parse()
        elif char == "\\":
            self.ptr += 1
            while len(self.stk):
                self.parse()
        else:
            self.execute(char, rest)

        while self.stk and sum(self.stk[1:]) / 2 > self.stk[0]:
            n = self.stk.pop(0) - 1
            if not self.num and not 0 <= n <= 0x10FFFF:
                raise HaltError
            self.io.print_value(n if self.num else chr(n))

        self.comm += 1
        if self.comm % 15 == 0:
            self.stk = []

    def step(self) -> None:
        """Execute one word, advancing the word pointer."""
        self.parse()
        self.ptr += 1


def run(source: str, io: IO) -> None:
    """Run a The Temporary Stack program."""
    state = State(io=io)
    state.code = source.split()

    while not state.halted:
        state.step()


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        data = f.read()

    run(data, IO())
