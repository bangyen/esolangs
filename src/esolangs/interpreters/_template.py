"""Template for a new esolang interpreter.

Copy to ``src/esolangs/interpreters/<category>/<name>.py`` and fill in the
dispatch.  The conventions every interpreter follows -- ``run(code, io)``,
:class:`ValueError` for a malformed program, :class:`~esolangs.exceptions.HaltError`
for an invalid operation, ``EOFError`` on exhausted input, a ``_Machine``
with ``step``/``halted``/``snapshot``, a pure :func:`_advance`, and the
module docstring shape ``tests/test_interpreter_conventions.py`` checks --
are listed under "Interpreter conventions" in ``docs/CONTRIBUTING.md``.
"""

import sys

from esolangs.interpreters.io import IO

#: The whole run state as an immutable value, so ``snapshot`` can hand it
#: out and the transition returns a new one.
type _State = tuple[int, int]


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
        return (self.ind, self.data, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the code position.

        The shell: the two ports live here and nothing else does.
        """
        c = self.code[self.ind]

        # A read is taken before the transition and passed as an argument.
        byte = None
        if c == ",":
            byte = self.io.input_char()
        elif c == ";":
            # ``input_str`` returns the raw line, and an empty one is legal:
            # guard before indexing.  Running out still raises EOFError.
            val = self.io.input_str()
            byte = ord(val[0]) if val else None

        self._state, out = _advance(self._state, self.code, byte)

        # The transition decides the write; the shell performs it.
        if out is not None:
            self.io.print_char(out)


def run(code: str, io: IO) -> None:
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
