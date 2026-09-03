"""Interpreter for Bitdeque.

PUSH/INJECT append a register value to the deque, POP/EJECT pop it (0 when
empty), INVERT flips the register, and GOTO jumps to a numbered command when
the register is nonzero.

The wiki says of this language that "there is (currently) no I/O", so
following the repo convention for interpreter-only languages (Minsky Swap
prints its registers), the deque contents are printed when the program ends
-- space-separated on one line.  Both the choice to print and the format are
this interpreter's, not the spec's.

The wiki says GOTO goes to the Nth operation but does not pin down the
indexing; this interpreter treats N as 0-based (GOTO 2 lands on the third
command, skipping the GOTO itself), matching its reference test.

The interpreter runs on a :class:`_Machine` (token cursor, register, and
deque), so it is step-capable: ``step()`` executes one token and ``halted``
is true once the cursor runs past the last token, making a GOTO loop a
finite-state cycle the state cycle detector can prove.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and a token to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.  The
deque is a tuple, so a state is a value that can be stored, compared, and
hashed as it stands.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what Bitdeque *does* stays in
the pure layer.  The one effect -- the end-of-run deque dump -- is done by
``step`` before it calls the pure transition.
"""

from __future__ import annotations

import re
import sys

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

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so the dump is necessarily the caller's business -- this
    function only records, through ``rendered``, that it has happened.

    PUSH and POP work the back of the deque; INJECT and EJECT work the
    front.  That pairing is what makes this a deque rather than a queue or
    a stack, so the four are deliberately spelled out rather than folded
    together.  Popping either end of an empty deque yields zero.

    GOTO is 0-based and only fires when the register is nonzero: it lands
    on ``num - 1`` so the shared increment below carries it to ``num``.
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


class _Machine:
    """Per-run Bitdeque state: the token cursor, register, and deque.

    ``step()`` executes one token; ``halted`` is true once the cursor passes
    the last token.  The VM and the state-cycle hang detector expose this
    object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Tokenize ``code`` and reset the register, deque, and cursor."""
        self.io = io
        lst = ("INJECT", "PUSH", "EJECT", "POP", "INVERT", r"GOTO *(\d+)")
        join = f"({'|'.join(lst)})"
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

        The print belongs to the step *after* the halt, as Minsky Swap and
        RAM0 already spell it, so that stepping a machine to a standstill
        writes what ``run`` writes.  Keeping it in ``run`` instead left the
        VM adapter to replicate it, which is how the two drifted apart in
        the first place.
        """
        ind, reg, deq, rendered = self.state
        if ind >= self.size:
            if not rendered:
                self.render()
                self.state = (ind, reg, deq, True)
            return
        self.state = _advance(self.state, self.tokens[ind][0])

    def render(self) -> None:
        """Print the deque contents, one value per space.

        No trailing newline: the wiki defines no I/O for Bitdeque at all, so
        there is no spec to be faithful to, and a newline here would be
        nothing but trailing whitespace.
        """
        self.io.print_str(" ".join(map(str, self.state[2])))


def run(code: str, io: IO) -> None:
    """Run a Bitdeque program and print the deque at the end."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step prints the deque


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
