"""Interpreter for BFStack.

Brainfuck commands on a stack: ``>`` pushes 0, ``<`` pops, ``+``/``-``
adjust the top (mod 256; the wiki gives no width), ``.`` prints it,
``,`` pushes a byte, ``[ ]`` loop while the top is nonzero.  An
empty-stack pop or output raises :class:`HaltError`; an unmatched ``[``
raises :class:`ValueError` when reached; exhausted input raises
:class:`EOFError`.  :func:`_advance` is pure and total over an
immutable ``_State``: :func:`_needs_operand` lets the shell reject an
empty-stack step first, and :func:`_forward_table` maps an unmatched
``[`` to ``None`` for the shell to raise on.
"""

from __future__ import annotations

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, stk, lst)`` -- the code cursor, the data
#: stack, and the loop stack.  A value, not a record: every transition below
#: returns a new one rather than editing one in place, and both stacks are
#: tuples for the same reason.
#:
#: The loop stack is state, not a scratch register: a ``]`` reads the
#: position a matching ``[`` pushed, so two runs sitting on the same
#: command with different loop stacks will go different places next.
#:
#: The code is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
type _State = tuple[int, tuple[int, ...], tuple[int, ...]]

#: The commands that read the top of the data stack, and so cannot run on
#: an empty one.  ``>`` pushes and ``,`` pushes, so neither needs an
#: operand; ``]`` needs a *loop* stack entry, which is checked separately.
_NEEDS_OPERAND = frozenset("<+-.[")


def _needs_operand(char: str) -> bool:
    """Whether ``char`` requires a non-empty data stack to run."""
    return char in _NEEDS_OPERAND


def _forward_table(code: str) -> dict[int, int | None]:
    """Map every ``[`` to its ``]``, or to ``None`` when it has none.

    Built once at load: scanning per skip was 95% of the worst row at nine
    inputs (502 skips over 2,080 characters, x2.8 per input against x2.0).
    Unmatched brackets are run-time errors, so this never raises.
    """
    table: dict[int, int | None] = {}
    stack: list[int] = []
    for ind, char in enumerate(code):
        if char == "[":
            stack.append(ind)
            table[ind] = None
        elif char == "]" and stack:
            table[stack.pop()] = ind
    return table


def _advance(
    state: _State, code: str, jumps: dict[int, int | None], byte: int | None = None
) -> _State:
    """Return the state after executing the command at the cursor.

    Pure and total; ``,``'s byte arrives as ``byte``.  ``]`` jumps to one
    before its ``[`` so the shared increment re-tests it.
    """
    ind, stk, lst = state
    char = code[ind]
    if char == ">":
        stk = (*stk, 0)
    elif char == "<":
        stk = stk[:-1]
    elif char == "+":
        stk = (*stk[:-1], (stk[-1] + 1) % 256)
    elif char == "-":
        stk = (*stk[:-1], (stk[-1] - 1) % 256)
    elif char == ",":
        stk = (*stk, byte if byte is not None else 0)
    elif char == "[":
        if stk[-1]:
            lst = (*lst, ind)
        else:
            # Skipping the loop: the shell resolved the match, so this
            # cannot fail here.
            target = jumps[ind]
            ind = target if target is not None else ind
    elif char == "]":
        ind, lst = lst[-1] - 1, lst[:-1]
    return (ind + 1, stk, lst)


class _Machine:
    """A BFStack run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str, io: IO) -> None:
        """Start with an empty data stack and loop stack."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(code)
        self._jumps = _forward_table(code)
        self.state: _State = (0, (), ())

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def stk(self) -> tuple[int, ...]:
        return self.state[1]

    @property
    def lst(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.size

    # The VM's language-shaped view.  BFStack's store *is* its data stack, so
    # ``stack`` carries it and ``memory`` is empty -- the loop stack is
    # control flow, not addressable state, and stays out of both.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """BFStack addresses no cells; its store is the stack."""
        return []

    @property
    def stack(self) -> list[int]:
        """The data stack, bottom first."""
        # A list, because that is the shape the VM's view is defined in.
        # It is a fresh one every time now, so a caller can no longer write
        # into a running machine -- the state's own tuple is unreachable.
        return list(self.state[1])

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Both stacks are already tuples, so they go in as they stand.
        ind, stk, lst = self.state
        return (stk, lst, ind, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        The two I/O effects and all three error cases are here.
        """
        if self.halted:
            return
        ind, stk, lst = self.state
        char = self.code[ind]
        if _needs_operand(char) and not stk:
            raise HaltError(
                f"{char!r} at position {ind} needs a value on the stack and "
                f"the stack is empty"
            )
        if char == "]" and not lst:
            raise HaltError(f"']' at position {ind} closes a loop that never opened")
        if char == "[" and not stk[-1] and self._jumps[ind] is None:
            # The original scanned the cursor to the end before it noticed
            # the bracket was unmatched, leaving the machine halted.  A
            # caller that catches the error still sees that, so the cursor
            # is moved here rather than left where the scan began.
            self.state = (self.size, stk, lst)
            raise ValueError("unmatched '['")
        byte = None
        if char == ".":
            self.io.print_char(chr(stk[-1]))
        elif char == ",":
            byte = self.io.input_char()
        self.state = _advance(self.state, self.code, self._jumps, byte)


def run(code: str, io: IO) -> None:
    """Run a BFStack program, halting on an invalid empty-stack operation."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
