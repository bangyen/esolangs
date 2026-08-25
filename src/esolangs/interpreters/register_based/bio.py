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
"""

import re
import sys

from esolangs.interpreters.io import IO

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
        self.reg: list[int] = [0] * 3
        self.stk: list[int] = []
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the command list."""
        return self.ind >= len(self.commands)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (tuple(self.reg), tuple(self.stk), self.ind, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the cursor."""
        if self.halted:
            return
        command = self.commands[self.ind]
        # A loop-open command carries the ``{`` that opens its body, so the
        # register is the triple's own last letter rather than the token's.
        r = "xyz".find(command[2]) if command != "};" else -1
        c = command[:2]

        if c == "0o":
            self.reg[r] += 1
        elif c == "1o":
            self.reg[r] -= 1
        elif c == "1i":
            # Handle negative values by converting to unsigned 8-bit
            self.io.print_char(chr(self.reg[r] % 256))
        elif command == "};":
            # ``parse`` matched the braces, so a ``}`` always has a loop.
            self.ind = self.stk.pop() - 1
        elif self.reg[r]:
            self.stk.append(self.ind)
        else:
            # Skip the loop block, counting braces rather than ``0i``
            # triples: the opener is the triple *with* its ``{``, and
            # ``parse`` has already matched them, so the closer exists.
            mat = 1
            while mat:
                self.ind += 1
                command = self.commands[self.ind]
                if command.endswith("{"):
                    mat += 1
                elif command == "};":
                    mat -= 1
        self.ind += 1


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
