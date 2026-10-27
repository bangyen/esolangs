"""Interpreter for NOR machine.

A program is a string of one-letter commands over a queue of unbounded
integers.  Every input integer is enqueued before the first command; the
program then runs from its first command to its last and starts over,
forever, until ``V`` finds a single value in the queue and prints it.

Commands:
    ``I``  dequeue a value and enqueue it
    ``A``  dequeue a value and enqueue it twice
    ``X``  dequeue A, then B; enqueue B, then A
    ``V``  dequeue A and B, enqueue ``~(A | B)``; alone, print and halt
    ``L``  dequeue a value and enqueue it shifted left by one
    ``R``  dequeue a value and enqueue it shifted right by one

Input/output:
    The whole input is read as whitespace-separated integers; ``V`` prints
    the remaining value's decimal digits.  No command reads, so there is no
    read at EOF: a short input is a shorter queue.

Errors:
    ProgramError: a character that is neither a command nor whitespace, or
        a program with no command.
    ArgumentError: an input token that is not an integer.
    HaltError: a command dequeuing more values than the queue holds.

Decisions:
    * The lone ``V`` prints the value itself: the page says it causes "it
      to be printed", and the queue holds nothing else to print.
    * Integers are unbounded two's complement, so ``V`` is Python's
      ``~(a | b)`` and ``R`` floors (``-1 >> 1`` is -1); the page says only
      that the machine "operates on integers".
    * Whitespace is skipped, and the three-letter names (``rot``, ``dup``,
      ...) are labels in the page's table, not source.
    * A program with no command is refused: it can never reach a ``V``, so
      the page's "loop forever" is its only behaviour.
    * ``V`` on an empty queue halts with an error rather than printing:
      the page's print needs exactly one value.
"""

from __future__ import annotations

import re
from collections import deque

from esolangs.exceptions import ArgumentError, HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.memory import parse_integer
from esolangs.runtime.source_hints import syntax_error

#: Values each command dequeues.
_POPS = {"I": 1, "A": 1, "X": 2, "V": 2, "L": 1, "R": 1}


def _advance(c: str, values: tuple[int, ...]) -> tuple[int, ...]:
    """Return what command ``c`` enqueues, given the values it dequeued.

    Pure: the shell owns the queue, which ``A`` can grow without bound.
    """
    if c == "I":
        return values
    if c == "A":
        return values * 2
    if c == "X":
        return values[::-1]
    if c == "V":
        return (~(values[0] | values[1]),)
    if c == "L":
        return (values[0] << 1,)
    return (values[0] >> 1,)


def _parse_inputs(text: str) -> deque[int]:
    """Return every whitespace-separated input integer, in order."""
    queue: deque[int] = deque()
    for token in text.split():
        # ASCII decimal only, as ``IO.input_num`` accepts.
        if not re.fullmatch(r"[+-]?[0-9]+", token):
            raise syntax_error(
                f"input must be integers, got {token!r}",
                "supply whitespace-separated decimal integers, for example 1 0",
                error_type=ArgumentError,
            )
        queue.append(parse_integer(token))
    return queue


class _Machine:
    """The run state: the command index, the queue and the halt flag."""

    # ``ind`` indexes the commands with whitespace removed.
    ip_shape = "opaque"

    #: A short input is a shorter queue, never a failed read.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        commands = "".join(code.split())
        for c in commands:
            if c not in _POPS:
                raise syntax_error(
                    f"unknown command {c!r}",
                    "use the letters I A X V L R; whitespace is ignored",
                )
        if not commands:
            raise syntax_error(
                "a program with no command loops forever",
                "end the program with V to print the last value",
            )
        self.commands = commands
        self.io = io
        self.ind = 0
        self.queue: deque[int] | None = None
        self.done = False

    @property
    def halted(self) -> bool:
        return self.done

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        queue = None if self.queue is None else tuple(self.queue)
        return (self.ind, queue, self.done, self.io.progress())

    def step(self) -> None:
        """Run one command; the input is enqueued before the first."""
        if self.done:
            return
        if self.queue is None:
            self.queue = _parse_inputs(self.io.input_all())
        queue = self.queue
        c = self.commands[self.ind]
        if c == "V" and len(queue) == 1:
            self.io.print_num(queue[0])
            self.done = True
            return
        if len(queue) < _POPS[c]:
            raise HaltError(
                f"{c!r} at command {self.ind} needs {_POPS[c]} value(s) and the "
                f"queue holds {len(queue)}",
                hint="input or keep enough values before dequeuing",
            )
        values = tuple(queue.popleft() for _ in range(_POPS[c]))
        queue.extend(_advance(c, values))
        self.ind = (self.ind + 1) % len(self.commands)


def run(code: str, io: IO) -> None:
    """Run a NOR machine program until a lone ``V`` prints."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
