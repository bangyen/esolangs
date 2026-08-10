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


def run(code: list[str], io: IO) -> None:
    """Run a Taglate program seeded by the first line's queue."""
    if not code:
        return
    queue = [ord(c) for c in code[0]]
    tokens = _tokens("".join(code[1:]))
    match = _match(tokens)

    def pop() -> int:
        """Pop the front of the queue, halting when it is empty."""
        if not queue:
            raise HaltError
        return queue.pop(0)

    ind = 0
    while ind < len(tokens):
        tok = tokens[ind]
        if tok == "a":
            queue.append((pop() + pop()) % 65536)
        elif tok == "b":
            x, y = pop(), pop()
            queue.append((x - y) % 65536)
        elif tok == "c":
            queue.append((pop() * pop()) % 65536)
        elif tok == "d":
            x, y = pop(), pop()
            if not y:
                raise HaltError
            queue.append(x // y)
        elif tok == "e":
            queue.append(pop())
        elif tok == "f":
            pop()
        elif tok == "gy":
            if not queue or queue[0] == 0:
                partner = match.get(ind)
                if partner is None:
                    raise ValueError("unmatched 'gy'")
                ind = partner
        elif tok == "gz":
            if queue and queue[0] != 0:
                partner = match.get(ind)
                if partner is None:
                    raise ValueError("unmatched 'gz'")
                ind = partner
        elif tok == "h":
            queue.append(io.input_char())
        elif tok == "i":
            io.print_char(chr(pop()))
        elif tok == "j":
            value = pop()
            queue.append((value - 1) % 65536 if value else 1)
        else:  # "t"
            queue = [ord(c) for c in _google_url(queue)]

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
