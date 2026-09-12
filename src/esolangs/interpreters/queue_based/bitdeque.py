r"""Interpreter for Bitdeque."""

from __future__ import annotations

import re
import sys

from esolangs.interpreters.io import IO

# : One instant of a run:.
# : the register, the deque,.
# : printed.
# : rather than editing one in.
#: same reason.
# :.
# : ``rendered`` is state.
# : happens *after* the cursor.
# : alone cannot tell "about to.
# : of ``snapshot``, which.
# :.
# : The tokens are deliberately.
# : but they *are* in.
# : removing them would change.
type _State = tuple[int, int, tuple[int, ...], bool]


def _advance(state: _State, sym: str) -> _State:
    r"""Return the state after executing one token."""
    ind, reg, deq, rendered = state
    if sym == "PUSH":
        deq = (*deq, reg)
    elif sym == "INJECT":
        deq = (reg, *deq)
    elif sym == "POP":
        reg, deq = (deq[-1], deq[:-1]) if deq else (0, deq)
    elif sym == "EJECT":
        reg, deq = (deq[0], deq[1:]) if deq else (0, deq)
    elif sym == "INVERT":
        reg ^= 1
    elif reg:
        ind = int(sym[4:]) - 1
    return (ind + 1, reg, deq, rendered)


def _reject_stray_text(code: str, pattern: re.Pattern[str]) -> None:
    r"""Refuse a word that is not one of the six commands."""
    end = 0
    for match in pattern.finditer(code):
        if stray := code[end : match.start()].strip():
            raise ValueError(
                f"{stray.split()[0]!r} is not a Bitdeque command; the "
                f"commands are INJECT, PUSH, EJECT, POP, INVERT and GOTO n, "
                f"in upper case"
            )
        end = match.end()
    if tail := code[end:].strip():
        raise ValueError(
            f"{tail.split()[0]!r} is not a Bitdeque command; the commands "
            f"are INJECT, PUSH, EJECT, POP, INVERT and GOTO n, in upper case"
        )


class _Machine:
    r"""Per-run Bitdeque state: the token cursor, register, and deque."""

    # : Whether the tape/registers.
    # : It belongs to the language,.
    # : ends its loop with one more.
    # : ``halted`` has driven the.
    #: its output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: str, io: IO) -> None:
        r"""Tokenize ``code`` and reset the register, deque, and cursor."""
        self.io = io
        lst = ("INJECT", "PUSH", "EJECT", "POP", "INVERT", r"GOTO *(\d+)")
        join = f"({'|'.join(lst)})"
        _reject_stray_text(code, re.compile(join))
        self.tokens = re.findall(join, code)
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        self.size = len(self.tokens)
        self.state: _State = (0, 0, (), False)

    # The language's own names.
    # than fields of their own, so.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def reg(self) -> int:
        return self.state[1]

    @property
    def deq(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def rendered(self) -> bool:
        r"""Whether the end-of-run deque dump has already been printed."""
        return self.state[3]

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has passed the last token."""
        return self.state[0] >= self.size

    # The VM's language-shaped.
    # register reads as a stack of.

    @property
    def ip(self) -> int:
        r"""The token cursor."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""The deque, front first."""
        return list(self.state[2])

    @property
    def stack(self) -> list[object]:
        r"""The single register, as a one-element stack."""
        return [self.state[1]]

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The fields this returned.
        # the same order.
        # states of a running machine.
        ind, reg, deq, _rendered = self.state
        return (tuple(self.tokens), ind, reg, deq, self.io.position())

    def step(self) -> None:
        r"""Execute one token, printing the deque once the cursor ends."""
        ind, reg, deq, rendered = self.state
        if ind >= self.size:
            if not rendered:
                self.render()
                self.state = (ind, reg, deq, True)
            return
        self.state = _advance(self.state, self.tokens[ind][0])

    def render(self) -> None:
        r"""Print the deque contents, one value per space."""
        self.io.print_str(" ".join(map(str, self.state[2])))


def run(code: str, io: IO) -> None:
    r"""Run a Bitdeque program and print the deque at the end."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step prints the.


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
