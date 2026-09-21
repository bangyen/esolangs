"""Interpreter for Taglate.

The first line seeds a queue of integers (0-65535, wrapping); the rest
hold commands: arithmetic ``a``-``d``, rotate/discard ``e``/``f``, loops
``gy``/``gz``, char I/O ``h``/``i``, ``j`` toggle-counter, and ``t``,
which replaces the queue with a Google Translate URL of its text.

Gaps decided: division by zero and popping an empty queue halt with
:class:`~esolangs.exceptions.HaltError`; an empty queue reads as 0 for
loop conditions; unmatched ``gy``/``gz`` raise :class:`ValueError`; a
non-command character (and a lone ``g``) is **skipped** -- so ``qqq``
runs cleanly -- because ``test_a_skipped_character_advances_the_cursor``
and its neighbours pin that deliberately, where Bitdeque, the other
queue language, refuses; ``t``
keeps the RFC 3986 unreserved set and ``%XX``-encodes the rest
(uppercase hex, wider above 255), narrower than the real page's
``!$'()*,/:;?@`` and ``+`` but within the spec.  Exhausted input raises
:class:`EOFError`.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.brackets import unmatched
from esolangs.interpreters.io import IO

_SINGLE = frozenset("abcdefhijt")


def _tokens(commands: str) -> list[str]:
    """Split a command string into tokens; ``gy``/``gz`` are two-char."""
    res: list[str] = []
    i = 0
    while i < len(commands):
        c = commands[i]
        if c == "g" and i + 1 < len(commands) and commands[i + 1] in "yz":
            res.append(commands[i : i + 2])
            i += 2
        elif c in _SINGLE:
            res.append(c)
            i += 1
        else:
            i += 1
    return res


def _match(tokens: list[str]) -> dict[int, int]:
    """Map each ``gy`` to its ``gz`` partner and vice versa."""
    stack: list[int] = []
    res: dict[int, int] = {}
    for i, tok in enumerate(tokens):
        if tok == "gy":
            stack.append(i)
        elif tok == "gz" and stack:
            j = stack.pop()
            res[j] = i
            res[i] = j
    return res


_URL_SAFE = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~",
)
_PREFIX = "https://translate.google.com/?sl=en&tl=es&text="
_SUFFIX = "&op=translate"


def _google_url(queue: list[int]) -> str:
    parts = [_PREFIX]
    for value in queue:
        char = chr(value)
        if char in _URL_SAFE:
            parts.append(char)
        else:
            parts.append(f"%{value:02X}")
    parts.append(_SUFFIX)
    return "".join(parts)


#: One instant of a run: ``(queue, ind)`` -- the queue of 16-bit values and
#: the token cursor.  A value the transitions below map forward, with the
#: queue as a ``tuple`` for the same reason.
#:
#: The tokens and their ``gy``/``gz`` pairing are not here: neither changes
#: during a run, so a step is given them rather than carrying them.
type _State = tuple[tuple[int, ...], int]


def _pop(state: _State) -> tuple[int, _State]:
    """Return the front value and the state without it.

    Raises :class:`HaltError` on an empty queue.
    """
    queue, ind = state
    if not queue:
        raise HaltError("the queue is empty, so there is nothing to pop")
    return (queue[0], (queue[1:], ind))


def _push(state: _State, value: int) -> _State:
    """Return ``state`` with ``value`` on the back of the queue."""
    queue, ind = state
    return ((*queue, value % 65536), ind)


def _advance(
    state: _State,
    tok: str,
    match: dict[int, int],
    byte: int | None = None,
) -> _State:
    """Return the state after executing ``tok``.

    Pure; ``i``'s value is popped here and handed back, ``h``'s byte
    arrives as ``byte``.  Popping is threaded so ``a``/``c`` on a one-value
    queue lose it before the second pop halts, as the original did.  ``d``
    does not wrap and halts on zero.
    """
    queue, ind = state
    if tok == "a":
        x, state = _pop(state)
        y, state = _pop(state)
        state = _push(state, (x + y) % 65536)
    elif tok == "b":
        x, state = _pop(state)
        y, state = _pop(state)
        state = _push(state, (x - y) % 65536)
    elif tok == "c":
        x, state = _pop(state)
        y, state = _pop(state)
        state = _push(state, (x * y) % 65536)
    elif tok == "d":
        x, state = _pop(state)
        y, state = _pop(state)
        if not y:
            raise HaltError(f"'d' divides {x} by the queued {y}, which is zero")
        state = _push(state, x // y)
    elif tok == "e":
        x, state = _pop(state)
        state = _push(state, x)
    elif tok == "f":
        _x, state = _pop(state)
    elif tok == "gy":
        if not queue or queue[0] == 0:
            state = (queue, _partner(match, ind, "gy"))
    elif tok == "gz":
        if queue and queue[0] != 0:
            state = (queue, _partner(match, ind, "gz"))
    elif tok == "h":
        state = _push(state, byte if byte is not None else 0)
    elif tok == "i":
        # The pop happens here; the caller prints what it finds missing.
        _x, state = _pop(state)
    elif tok == "j":
        value, state = _pop(state)
        state = _push(state, (value - 1) % 65536 if value else 1)
    else:  # "t"
        state = (tuple(ord(c) for c in _google_url(list(queue))), ind)

    return (state[0], state[1] + 1)


def _partner(match: dict[int, int], ind: int, tok: str) -> int:
    """Return the token index ``ind`` jumps to, rejecting an unmatched one."""
    partner = match.get(ind)
    if partner is None:
        # The position is the *token* index, which is what Taglate counts:
        # its program is a token list, not a character string.
        raise unmatched(tok, ind)
    return partner


#: How many values a token pops before it can fail.  ``d`` takes both of
#: its operands before testing the divisor, so a halt on division by zero
#: has still consumed two.
_POPS = {"a": 2, "b": 2, "c": 2, "d": 2, "e": 1, "f": 1, "i": 1, "j": 1}


def _consumed(state: _State, tok: str) -> _State:
    """Return the state a halting ``tok`` leaves behind.

    Drops as many values as the queue held, up to what the token wanted.
    """
    queue, ind = state
    return (queue[min(_POPS.get(tok, 0), len(queue)) :], ind)


class _Machine:
    """Per-run Taglate state: the queue, the token list, and the cursor.

    A loop whose head never zeroes is a finite-state cycle the hang
    detector can prove.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Seed the queue from the first line and tokenize the rest."""
        self.io = io
        self.queue: tuple[int, ...] = (
            tuple(ord(c) % 65536 for c in code[0]) if code else ()
        )
        self.tokens = _tokens("".join(code[1:]))
        self.match = _match(self.tokens)
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has passed the last token."""
        return self.ind >= len(self.tokens)

    # The VM's language-shaped view: Queue + token cursor; ip the cursor, memory the
    # queue.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.queue)

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.queue, self.ind, self.io.position())

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transitions work on."""
        return (self.queue, self.ind)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        self.queue, self.ind = state

    def step(self) -> None:
        """Execute one token, advancing the cursor.

        ``i`` prints the value the transition is about to pop, read before
        the call.  A failed step still writes the state back, so the queue
        is left as the original left it.
        """
        if self.halted:
            return
        tok = self.tokens[self.ind]

        byte = self.io.input_char() if tok == "h" else None
        if tok == "i" and self.queue:
            self.io.print_char(chr(self.queue[0]))

        state = self._state
        try:
            self._restore(_advance(state, tok, self.match, byte))
        except HaltError:
            # The pops that succeeded before the halt still happened.
            self._restore(_consumed(state, tok))
            raise


def run(code: list[str], io: IO) -> None:
    """Run a Taglate program seeded by the first line's queue."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
