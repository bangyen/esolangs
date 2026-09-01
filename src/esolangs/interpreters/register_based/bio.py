"""BIO (Binary IO) interpreter implementation.

Register-based esoteric language with three memory blocks (x, y, z).
Uses commands in format [0|1][O|I][x|y|z] for increment/decrement, loops, and output.

The wiki writes a loop as ``0i{ do something };`` and says every command is
ended by a ``;``, so neither mark is free-standing punctuation: a command
is a triple *with* its terminator, and a loop-open is a triple carrying the
``{`` that opens its body.  :data:`_COMMAND` matches them that way, which
is what makes a missing ``;`` or ``{`` a load error rather than a program
that quietly runs as something else.  Only ``//`` comments are dropped.

This is stricter than the page's Thutu contribution, which strips ``;``
and matches a bare ``0ix``; that is a third-party sketch marked untested
rather than the language author's implementation, so the prose and the
worked examples -- which agree, and always write both marks -- are what
the parser follows.

The interpreter runs on a :class:`_Machine` (the three registers, the loop
stack, and the command cursor), so it is step-capable: ``step()`` executes
one command and ``halted`` is true once the cursor reaches the end of the
command list.  A loop whose body never changes a register grows the loop
stack and cursor without revisiting a snapshot only when a register grows
unboundedly (the ``run()`` backstop's class); a loop that revisits a
snapshot is proven by the state-cycle hang detector.

The braces are checked when the program loads, so a malformed one is
rejected with :class:`ValueError` before it runs: a loop with no matching
``}``, a ``}`` closing nothing, a ``0i`` without its ``{``, and any other
character the language does not define.  Because that check runs first,
the loop stack can never be popped empty at run time.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the command list to the next state, and
never mutates what it is given.  It takes no ``io`` argument at all, so it
is total and side-effect free by construction rather than by inspection.

Nothing needs hoisting out of it beyond the one print: the load check has
already rejected every malformed program, so no command can fail at run
time and the transition has no error case of its own.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what BIO *does* stays in the
pure layer.
"""

from __future__ import annotations

import re
import sys

from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, reg, stk)`` -- the command cursor, the
#: three registers, and the loop-return stack.  A value, not a record:
#: every transition below returns a new one rather than editing one in
#: place, and both stores are tuples for the same reason.
#:
#: The commands are deliberately not in here.  They do not change during a
#: run, so carrying them would put constant data in every value the cycle
#: detector stores.  They are a parameter to the transition instead.
#:
#: The field order starts ``ind`` for consistency with the rest of the
#: series, but ``snapshot`` still returns ``(reg, stk, ind, ...)`` -- the
#: order it always returned.
type _State = tuple[int, tuple[int, int, int], tuple[int, ...]]


def _bumped(reg: tuple[int, int, int], index: int, delta: int) -> tuple[int, int, int]:
    """Return ``reg`` with register ``index`` moved by ``delta``."""
    values = list(reg)
    values[index] += delta
    return (values[0], values[1], values[2])


def _skip(commands: list[str], ind: int) -> int:
    """Return the index of the ``};`` closing the loop opened at ``ind``.

    Braces are counted rather than ``0i`` triples: the opener is the triple
    *with* its ``{``, and ``parse`` has already matched them, so the closer
    exists and this cannot run off the end.
    """
    mat = 1
    while mat:
        ind += 1
        if commands[ind].endswith("{"):
            mat += 1
        elif commands[ind] == "};":
            mat -= 1
    return ind


# A BIO command: an increment/decrement/output triple ended by its ``;``, a
# loop-open triple carrying the ``{`` that opens its body, or the ``};``
# that closes one.  The wiki writes the loop as ``0i{ do something };`` and
# says every command is ended by a ``;``, so both belong to the command
# rather than being free-standing punctuation -- and a triple missing
# either is not a command at all.
_COMMAND = re.compile(r"[01][oOiI][xXyYzZ](?:\{|;)|\};")

# Comments run from ``//`` to the end of the line and carry no meaning, so
# they are removed before the program is tokenized.
_COMMENT = re.compile(r"//[^\n]*")


def parse(code: str) -> list[str]:
    """Return ``code``'s commands, lowercased, or raise on a malformed program.

    Comments are stripped, then what remains must be commands and
    whitespace with nothing left over.  A triple without its terminator, a
    ``0i`` without its ``{``, and a stray character alike are load errors
    rather than something silently skipped -- the interpreter used to keep
    only its regex's matches and drop the rest, so a typo ran as a
    different program.  The braces are matched here too, so
    :class:`_Machine` can assume every ``}`` has a loop to close.
    """
    stripped = _COMMENT.sub("", code)
    commands = [match.group().lower() for match in _COMMAND.finditer(stripped)]
    if "".join(commands) != "".join(stripped.lower().split()):
        raise ValueError("BIO: not a command")
    depth = 0
    for command in commands:
        if command.endswith("{"):
            depth += 1
        elif command == "};":
            if not depth:
                raise ValueError("BIO: '}' closes no loop")
            depth -= 1
    if depth:
        raise ValueError("BIO: unmatched '{'")
    return commands


class _Machine:
    """Per-run BIO state: the registers, the loop stack, and the cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the command list.  The VM and the state-cycle hang
    detector expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into commands and reset the registers."""
        self.io = io
        self.commands = parse(code)
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(self.commands)
        self.state: _State = (0, (0, 0, 0), ())

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def reg(self) -> tuple[int, int, int]:
        """The three registers, x then y then z."""
        return self.state[1]

    @property
    def stk(self) -> tuple[int, ...]:
        """The loop-return stack."""
        return self.state[2]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the command list."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: Registers + loop stack + cursor; ip the cursor,
    # memory the regs.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.state[1])

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.state[2])

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Both stores are already tuples, in the order this returned before
        # the fields moved into a state value.
        ind, reg, stk = self.state
        return (reg, stk, ind, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        The one print lives here rather than in the transition: this is the
        shell, so it is where an effect belongs.  Nothing else needs
        hoisting -- the load check has rejected every malformed program, so
        no command can fail once a run has started.
        """
        ind, reg, _stk = self.state
        if ind >= self.size:
            return
        command = self.commands[ind]
        if command[:2] == "1i":
            # Handle negative values by converting to unsigned 8-bit
            self.io.print_char(chr(reg["xyz".find(command[2])] % 256))
        self.state = _advance(self.state, self.commands)


def _advance(state: _State, commands: list[str]) -> _State:
    """Return the state after executing one command.

    Pure, and total: ``parse`` has already matched every brace, so a ``};``
    always has a loop to return to and a skip always finds its closer.  It
    takes no ``io`` argument, so ``1i``'s print is the caller's business --
    it changes no state at all.

    A ``};`` returns to one before the command that opened the loop, so the
    shared increment lands back *on* the opener and re-tests its register.
    """
    ind, reg, stk = state
    command = commands[ind]
    # A loop-open command carries the ``{`` that opens its body, so the
    # register is the triple's own last letter rather than the token's.
    r = "xyz".find(command[2]) if command != "};" else -1
    code = command[:2]

    if code == "0o":
        reg = _bumped(reg, r, 1)
    elif code == "1o":
        reg = _bumped(reg, r, -1)
    elif code == "1i":
        pass  # the print already happened in the shell
    elif command == "};":
        ind, stk = stk[-1] - 1, stk[:-1]
    elif reg[r]:
        stk = (*stk, ind)
    else:
        ind = _skip(commands, ind)
    return (ind + 1, reg, stk)


def run(code: str, io: IO) -> None:
    """Execute BIO code and produce output."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
