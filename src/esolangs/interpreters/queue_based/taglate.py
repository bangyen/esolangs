"""Interpreter for Taglate.

Taglate is a queue-based language: the first line seeds a queue of integers
(0-65535, wrapping), and the remaining lines hold commands.  Commands do
queue arithmetic (``a``-``d``), rotate and discard (``e``/``f``), loops
(``gy``/``gz``), character I/O (``h``/``i``), a toggle-counter trick
(``j``), and ``t``, which replaces the queue with a Google Translate URL of
its text.

Decisions for gaps in the wiki spec (documented):
- division by zero halts the program (it is an invalid operation, so the
  interpreter does not invent a result for it);
- an empty queue reads as 0 for loop conditions;
- popping an empty queue in an arithmetic or I/O command is an invalid
  operation and halts the program with
  :class:`~esolangs.exceptions.HaltError`;
- an unmatched ``gy``/``gz`` is a malformed program and is rejected with
  :class:`ValueError`;
- ``t`` keeps ASCII letters, digits, and ``-_.~`` (the RFC 3986 unreserved
  set), encoding everything else as ``%XX`` (uppercase hex, more digits for
  values above 255).  This is a deliberate conservative choice: the real
  translate page also leaves ``!$'()*,/:;?@`` literal and uses ``+`` for
  spaces, but the wiki spec only requires URL-safe characters to survive, so
  encoding the extra characters too is safe and simpler.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys

from esolangs.exceptions import HaltError
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

    Raises :class:`HaltError` on an empty queue, which is what makes
    popping one an invalid operation rather than a zero.
    """
    queue, ind = state
    if not queue:
        raise HaltError
    return (queue[0], (queue[1:], ind))


def _push(state: _State, value: int) -> _State:
    """Return ``state`` with ``value`` on the back of the queue."""
    queue, ind = state
    return ((*queue, value), ind)


def _advance(
    state: _State,
    tok: str,
    match: dict[int, int],
    byte: int | None = None,
) -> _State:
    """Return the state after executing ``tok``.

    Pure: it reads ``state`` and returns a new one.  ``i``'s printing is
    the caller's business -- the value it prints is popped here and handed
    back through the state -- and ``h``'s byte arrives as ``byte``.

    Popping is threaded rather than mutating, which matters for the four
    commands that pop twice in one expression.  ``a`` and ``c`` consumed
    the first value before discovering the queue was too short, leaving it
    empty and the cursor unmoved; raising from the *second* ``_pop`` on a
    state that already lost the first reproduces exactly that.

    ``d`` is the one arithmetic command that does not wrap, and a zero
    divisor halts rather than inventing a result.
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
            raise HaltError
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
        raise ValueError(f"unmatched '{tok}'")
    return partner


#: How many values a token pops before it can fail.  ``d`` takes both of
#: its operands before testing the divisor, so a halt on division by zero
#: has still consumed two.
_POPS = {"a": 2, "b": 2, "c": 2, "d": 2, "e": 1, "f": 1, "i": 1, "j": 1}


def _consumed(state: _State, tok: str) -> _State:
    """Return the state a halting ``tok`` leaves behind.

    The original popped straight off the queue, so the values taken before
    the halt were gone and the cursor had not moved.  This drops the same
    ones: as many as the queue actually held, up to what the token wanted.
    """
    queue, ind = state
    return (queue[min(_POPS.get(tok, 0), len(queue)) :], ind)


class _Machine:
    """Per-run Taglate state: the queue, the token list, and the cursor.

    ``step()`` executes one token; ``halted`` is true once the cursor passes
    the last token.  ``t`` rebuilds the queue from the URL, and ``gy``/``gz``
    move the cursor to a partner, so a loop whose head never zeroes is a
    finite-state cycle the state-cycle hang detector can prove.  The VM and
    the hang detector expose this object.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Seed the queue from the first line and tokenize the rest."""
        self.io = io
        self.queue: tuple[int, ...] = tuple(ord(c) for c in code[0]) if code else ()
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
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- the VM's views and
        the tests read them -- so they stay; the one assignment a step
        makes is here rather than scattered through the rules above.
        """
        self.queue, self.ind = state

    def step(self) -> None:
        """Execute one token, advancing the cursor.

        The two ports live here rather than in the transition: this is the
        shell.  ``h``'s byte is read here and handed over, and ``i`` prints
        the value the transition is about to pop -- read before the call,
        since the transition returns the queue without it.

        A failed step still moves the queue.  ``a`` and ``c`` pop twice, so
        a one-value queue loses that value before the halt, and the
        original left it that way; the state is written back on the way out
        so the machine is left where the old code left it.
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
