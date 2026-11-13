# Template for a new esolang interpreter; `just new-language` copies it to
# src/esolangs/languages/<name>/interpreter.py with <Language> filled in.
# The conventions -- run(code, io), ValueError for a malformed program,
# HaltError for an invalid operation, EOFError on exhausted input (unless the
# spec gives EOF a value: then eof= on its LANGUAGE), a _Machine with
# step/halted/snapshot, a pure _advance -- are under "Interpreter conventions"
# in docs/CONTRIBUTING.md.  The docstring below is the spec's shape
# (describe()["spec"]): fill each <describe ...> or delete its section;
# `scripts/new_language.py check` flags any left.  Errors: names the public
# exception a caller catches; give each entry a trigger in the language's
# tests/cases.toml (tests/interpreters/test_spec_triggers.py).
"""Interpreter for <Language>.

<describe the source syntax, state, one step, halt and output, in prose>

Commands:
    <describe each command on one line, only where a table helps>

Input/output:
    <describe the input unit and output, and what a read at EOF does>

Errors:
    ProgramError: <describe a malformed program; raised as ValueError>
    InputExhaustedError: <describe a read at EOF; raised as EOFError>
    ArgumentError: <describe a numeric read given a non-integer token>
    HaltError: <describe each invalid runtime operation>
    InterpreterLimitError: <describe recursion or memory exhaustion>

Decisions:
    * <describe each spec gap and the reading chosen, with its evidence>
"""

from collections.abc import Mapping
from typing import Any

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import Completion, CompletionReport
from esolangs.runtime._machine import MachineFactory
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime.io import IO

#: The whole run state as an immutable value, so ``snapshot`` can hand it
#: out and the transition returns a new one.
type _State = tuple[int, int]


# Keep the name, even for a one-step language: the purity test
# (tests/interpreters/test_transition_purity.py) finds the core by it.
def _advance(
    state: _State, code: str, byte: int | None = None
) -> tuple[_State, str | None]:
    """Return the state after one command, and the character to print.

    Pure: a read arrives as ``byte``, a write leaves as the return value.
    """
    ind, data = state
    c = code[ind]
    out = None
    if c == "+":  # placeholder: increment the data cell
        data = (data + 1) % 256
    elif c == ".":  # placeholder: print the data cell
        out = chr(data)
    elif c in ",;" and byte is not None:  # store the byte the shell read
        data = byte
    # add the language's real instructions here
    return (ind + 1, data), out


class _Machine:
    """The run state: the data cell and the code position."""

    # ``ind`` counts source characters.  If it indexes anything else (parsed
    # tokens, a grid, a frame stack), set ``ip_shape`` -- see ``vm.ip_shape``.

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.data = 0
        self.ind = 0

    @property
    def halted(self) -> bool:
        return self.ind >= len(self.code)

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.ind, self.data)

    @_state.setter
    def _state(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        self.ind, self.data = state

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Every field ``step`` can change, plus the input cursor: a repeat
        # that ignores consumed input is not a real cycle.
        return (self.ind, self.data, self.io.progress())

    def step(self) -> None:
        """Execute one command, advancing the code position.

        The shell: the two ports live here and nothing else does.
        """
        # A halted machine ignores a further step (``registry/_contracts.py`` checks).
        if self.halted:
            return
        c = self.code[self.ind]

        # A read is taken before the transition and passed as an argument.
        byte = None
        if c == ",":
            byte = self.io.input_char()
        elif c == ";":
            # ``input_str`` returns the raw line, and an empty one is legal:
            # guard before indexing.  Running out still raises EOFError; a
            # language with an EOF value catches it here and uses that value.
            val = self.io.input_str()
            byte = ord(val[0]) if val else None

        self._state, out = _advance(self._state, self.code, byte)

        # The transition decides the write; the shell performs it.
        if out is not None:
            self.io.print_char(out)


def prepare_machine(
    source: RunnerProgram, options: Mapping[str, Any]
) -> MachineFactory:
    """Bind text; each IO port receives fresh machine state."""
    if not isinstance(source, str):
        raise TypeError("machines require text source")
    if options:
        raise TypeError("machines accept no runtime options")

    def build(io: IO) -> _Machine:
        return _Machine(source, io)

    return build


def _execute(code: str, io: IO) -> CompletionReport:
    machine = _Machine(code, io)
    return drive(machine, policy=Completion.HALTED)


def run(code: str, io: IO) -> None:
    """Run ``code`` to completion on ``io``."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
