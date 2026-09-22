"""Interpreter for Bitdeque.

PUSH/INJECT append the register to the deque, POP/EJECT pop it (0 when
empty), INVERT flips the register, GOTO jumps to a 0-based command when
it is nonzero (GOTO 2 lands on the third command).  The wiki has no I/O,
so the deque is printed space-separated when the program ends -- the
repo's convention.  A word that is not one of the six upper-case commands
raises :class:`ValueError` (the old tokenizer ran a lower-case program
as nothing).  :func:`_advance` is pure over an immutable ``_State``; the
dump is the shell's post-halt step.
"""

from __future__ import annotations

import re

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, reg, deq, rendered)`` -- the token cursor,
#: the register, the deque, and whether the end-of-run dump has been
#: printed.  A value, not a record: every transition below returns a new one
#: rather than editing one in place, and the deque is a ``tuple`` for the
#: same reason.
#:
#: ``rendered`` is state because the dump is a once-per-run effect that
#: happens *after* the cursor has passed the last token, so the position
#: alone cannot tell "about to print" from "already printed".  It stays out
#: of ``snapshot``, which reports the fields it always reported.
#:
#: The tokens are deliberately not in the transition's view of the world,
#: but they *are* in ``snapshot`` -- which is where they already were, and
#: removing them would change every hash the cycle detector has stored.
type _State = tuple[int, int, tuple[int, ...], bool]


def _advance(state: _State, sym: str) -> _State:
    """Return the state after executing one token.

    PUSH/POP work the back, INJECT/EJECT the front -- a deque.  GOTO lands
    on ``num - 1`` so the shared increment carries it to ``num``.
    """
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
    """Refuse a word that is not one of the six commands.

    ``findall`` kept what matched: ``push invert push`` ran as nothing and
    exited 0, and a seventh word is never deliberate.
    """
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
    """Per-run Bitdeque state: the token cursor, register, and deque."""

    #: Whether the tape/registers are written on the step *after* the halt.
    #: It belongs to the language, not to whoever is stepping it: ``run``
    #: ends its loop with one more ``step()``, so a caller who stops at
    #: ``halted`` has driven the program correctly and still holds none of
    #: its output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: str, io: IO) -> None:
        """Tokenize ``code`` and reset the register, deque, and cursor."""
        self.io = io
        lst = ("INJECT", "PUSH", "EJECT", "POP", "INVERT", r"GOTO *(\d+)")
        join = f"({'|'.join(lst)})"
        _reject_stray_text(code, re.compile(join))
        self.tokens = re.findall(join, code)
        # ``halted`` is read twice per token -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(self.tokens)
        self.state: _State = (0, 0, (), False)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

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
        """Whether the end-of-run deque dump has already been printed."""
        return self.state[3]

    @property
    def halted(self) -> bool:
        """Whether the cursor has passed the last token."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: the deque is the store, and the one
    # register reads as a stack of one.

    @property
    def ip(self) -> int:
        """The token cursor."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The deque, front first."""
        return list(self.state[2])

    @property
    def stack(self) -> list[object]:
        """The single register, as a one-element stack."""
        return [self.state[1]]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The fields this returned before ``rendered`` joined the state, in
        # the same order.  ``rendered`` stays out: the detector compares
        # states of a running machine.
        ind, reg, deq, _rendered = self.state
        return (tuple(self.tokens), ind, reg, deq, self.io.position())

    def step(self) -> None:
        """Execute one token, printing the deque once the cursor ends.

        The print is the post-halt step, as Minsky Swap and RAM0 spell it.
        """
        ind, reg, deq, rendered = self.state
        if ind >= self.size:
            if not rendered:
                self.render()
                self.state = (ind, reg, deq, True)
            return
        self.state = _advance(self.state, self.tokens[ind][0])

    def render(self) -> None:
        """Print the deque contents, one value per space, no trailing newline."""
        self.io.print_str(" ".join(map(str, self.state[2])))


def run(code: str, io: IO) -> None:
    """Run a Bitdeque program and print the deque at the end."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step prints the deque


if __name__ == "__main__":
    script_main(run)
