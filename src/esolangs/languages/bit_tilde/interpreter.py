"""Interpreter for bit~.

An 8-cell bit pool with a pointer: ``~`` flips, ``>``/``<`` move (``>`` extends the
pool when the window would run past the end; ``<`` at cell 0 prepends a zero cell,
as the wiki's bare "move ... to the left" reads for every tape here), ``)`` reads a
byte and XORs it, MSB first, into the 8-bit window -- the spec says it "flip[s] the
current bit and the next 7 bits ... according to the ASCII character code" -- ``(``
prints that window ("the current bit and the next 7 bits"), ``{``/``}`` loop on the
current bit.  Other characters are ignored.  ``)`` reads newlines too.  A loop that
keeps extending the pool never repeats a state, so ``esolangs.run``'s ``timeout`` is
the guard.

Errors:
    ProgramError: an unmatched bracket, when it would jump (the Ruby port looped).
    InputExhaustedError: ``)`` at EOF (the cross-check exits 3).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from typing import Any

from esolangs.languages.bit_tilde.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.brackets import unmatched
from esolangs.runtime.io import IO

#: One instant of a run: ``(ind, cell, tape)`` -- the code cursor, the
#: pointer, and the bit pool.  A value, not a record: every transition below
#: returns a new one rather than editing one in place, and the pool is a
#: ``tuple`` for the same reason.
#:
#: The code is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
#:
#: The field order starts ``ind, cell`` for readability, but ``snapshot``
#: still returns ``(tape, cell, ind, ...)`` -- the order it always returned.
#: Reordering there would silently reorder every stored hash.
type _State = tuple[int, int, tuple[int, ...]]


def _grown(tape: tuple[int, ...], need: int) -> tuple[int, ...]:
    """Return ``tape`` extended with zeros to at least ``need`` cells."""
    return tape if need <= len(tape) else (*tape, *([0] * (need - len(tape))))


def _match(code: str, ind: int, step: int) -> int:
    """Return the index of the bracket matching ``code[ind]``.

    ``step`` 1 forward, -1 back; no match is ``ValueError``.
    """
    start = ind
    depth = step
    while depth:
        ind += step
        if not 0 <= ind < len(code):
            # The scan walks away from the bracket, so the position named
            # is the one it started from -- the bracket that has no match,
            # not wherever the walk fell off the code.
            raise unmatched(code[start], start)
        if code[ind] == "{":
            depth += 1
        elif code[ind] == "}":
            depth -= 1
    return ind


# :func:`_advance` is pure over an immutable ``_State``; the shell reads, prints and
# resolves the jump via :func:`_match`, the one part that can fail.
def _advance(
    state: _State,
    code: str,
    byte: int | None = None,
    target: int | None = None,
) -> _State:
    """Return the state after executing the character at the cursor.

    Pure and total: the shell has read the byte and resolved ``target``,
    which lands on the match because the shared increment steps past it.
    """
    ind, cell, tape = state
    char = code[ind]
    if char == "~":
        tape = (*tape[:cell], tape[cell] ^ 1, *tape[cell + 1 :])
    elif char == ">":
        # ``(`` reads eight cells, so the pool keeps them under the new cell.
        cell += 1
        tape = _grown(tape, cell + 8)
    elif char == "<":
        # At cell 0 the pool grows a zero cell on the left; see the docstring.
        if cell:
            cell -= 1
        else:
            tape = (0, *tape)
    elif char == ")":
        bits = tuple(int(b) for b in f"{byte if byte is not None else 0:08b}")
        tape = _grown(tape, cell + 8)
        window = tuple(a ^ b for a, b in zip(tape[cell : cell + 8], bits, strict=True))
        tape = (*tape[:cell], *window, *tape[cell + 8 :])
    elif target is not None:
        # Both brackets, once the shell has decided a jump happens.
        ind = target
    return (ind + 1, cell, tape)


_WORKSPACE_MODEL = WorkspaceModel(
    "bit-tilde-v1", ("tape", "pointer", "instruction", "input_cursor")
)


class _Machine:
    """Per-run bit~ state: the bit pool, the pointer, and the cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Start with an eight-cell pool at the origin."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per character -- once by ``run``'s loop
        # and once by ``step``'s guard -- so the length is taken once here.
        self.size = len(code)
        self.state: _State = (0, 0, (0,) * 8)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def cell(self) -> int:
        return self.state[1]

    @property
    def tape(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: Bit pool + pointer; ip the cursor, memory the pool.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.state[2])

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        return _WORKSPACE_MODEL.capture(
            tape=self.state[2],
            pointer=self.state[1],
            instruction=self.state[0],
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The pool is already a tuple, so it goes in as it stands, in the
        # order this returned before the fields moved into a state value.
        ind, cell, tape = self.state
        return (tape, cell, ind, self.io.progress())

    def step(self) -> None:
        """Execute one character, advancing the cursor.

        The shell does I/O and the bracket search, only when the bracket would jump.
        """
        if self.halted:
            return
        ind, cell, tape = self.state
        char = self.code[ind]
        byte = target = None
        if char == ")":
            byte = self.io.input_char() % 256  # As Boolfuck: a byte, not U+0100.
        elif char == "(":
            val = tape[cell : cell + 8]
            self.io.print_char(chr(int("".join(map(str, val)), 2)))
        elif char == "{" and not tape[cell]:
            target = _match(self.code, ind, 1)
        elif char == "}" and tape[cell]:
            target = _match(self.code, ind, -1)
        self.state = _advance(self.state, self.code, byte, target)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Bind source; each IO-bound construction owns fresh runtime state."""
    if not isinstance(source, str):
        raise TypeError("bit_tilde machines require text source")
    if options:
        raise TypeError("bit_tilde machines accept no runtime options")

    return RuntimePlan(partial(_Machine, source), partial(_execute, source))


def _execute(code: str, io: IO) -> CompletionReport:
    """Run a bit~ program."""
    machine = _Machine(code, io)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a bit~ program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
