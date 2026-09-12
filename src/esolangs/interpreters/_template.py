r"""Template for a new esolang interpreter."""

import sys

from esolangs.interpreters.io import IO

# : The whole run state as a.
# : real language's is bigger.
# : but it stays a *value*, so.
# : transition below can return.
type _State = tuple[int, int]


def _advance(
    state: _State, code: str, byte: int | None = None
) -> tuple[_State, str | None]:
    r"""Return the state after one command, and the character to print."""
    ind, data = state
    c = code[ind]
    out = None
    if c == "+":  # placeholder: increment the.
        data = (data + 1) % 256
    elif c == ".":  # placeholder: print the data.
        out = chr(data)
    elif c in ",;" and byte is not None:  # store the byte the shell read.
        data = byte
    # add the language's real.
    return (ind + 1, data), out


class _Machine:
    r"""The run state: the data cell and the code position."""

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
        r"""The machine's fields as the value the transition works on."""
        return (self.ind, self.data)

    @_state.setter
    def _state(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        self.ind, self.data = state

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # Every field ``step`` can.
        # that ignores consumed input.
        return (self.ind, self.data, self.io.position())

    def step(self) -> None:
        r"""Execute one command, advancing the code position."""
        c = self.code[self.ind]

        # A read is decided from the.
        # before the transition, which.
        byte = None
        if c == ",":
            byte = self.io.input_char()
        elif c == ";":
            # ``input_char`` handles the.
            # ``input_str`` hands back the.
            # (the user pressed Enter), so.
            # Enter is an IndexError.
            # different case, and still.
            val = self.io.input_str()
            byte = ord(val[0]) if val else None

        self._state, out = _advance(self._state, self.code, byte)

        # A write reports what the.
        # transition itself performs no.
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
