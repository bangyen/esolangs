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


#: One instant of a run: ``(acc, ind, skp, stk, halted)`` -- the
#: accumulator, the cursor, the break flag, the stack of loop-entry
#: positions, and whether ``&`` fired.  A value :func:`_advance` maps
#: forward, with the stack as a ``tuple`` for the same reason.
#:
#: ``skp`` is state, not a detail of one command.  ``*`` sets it and a
#: *later* ``[`` reads it to decide whether to enter its loop or jump past
#: it, so the flag outlives the command that raised it -- which is what
#: makes a break escape a whole nest rather than one level.
#:
#: The code is not here: Sophie never rewrites itself, so a step is handed
#: the program rather than carrying it.
type _State = tuple[int, int, bool, tuple[int, ...], bool]


def _advance(state: _State, code: str, value: int | None = None) -> _State:
    """Return the state after executing the command under the cursor.

    Pure: it reads ``state`` and returns a new one.  The four I/O commands
    are the caller's -- ``.`` and ``,`` print the accumulator this carries
    forward unchanged, and ``:``/``;`` arrive as ``value``, already read
    and already rejected if the input did not qualify, in which case it is
    ``None`` and the accumulator stands.

    Two jumps land deliberately short.  ``]`` and ``*`` return to one
    before the loop's ``[`` so the trailing advance re-reads it, and a
    conditional that fails jumps to its block's ``}`` -- or to the ``{`` of
    an else-block if one follows, so the trailing advance enters it.
    """
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
            raise HaltError
        ind = stk[-1] - 1
        stk = stk[:-1]
        if c == "*":
            skp = True
    elif c in ".,":
        pass  # printed by the caller; the accumulator is unchanged
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
    """Return the cursor for a conditional, entered or skipped.

    A taken branch steps over the ``@c`` header onto its block.  A failed
    one jumps to the block's close, and one place further when an
    else-block starts there, so the trailing advance lands inside it.
    """
    if taken:
        return ind + width
    end = find(code, ind + width)
    if end + 1 < len(code) and code[end + 1] == "{":
        return end + 1
    return end


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
        self.stk: tuple[int, ...] = ()
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
            self.stk,
            self._halted_by_command,
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.acc, self.ind, self.skp, self.stk, self._halted_by_command)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- the VM's views and
        the tests read them -- so they stay; the one assignment a step
        makes is here rather than scattered through the rules above.
        """
        self.acc, self.ind, self.skp, self.stk, self._halted_by_command = state

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the cursor.

        The four I/O commands live here rather than in the transition: this
        is the shell.  ``.`` and ``,`` print the accumulator the transition
        carries forward unchanged, and ``:``/``;`` read here -- including
        the test that decides whether the input counts, since an input that
        does not qualify must leave the accumulator alone rather than
        writing a zero over it.
        """
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
    """Execute Sophie program code."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
