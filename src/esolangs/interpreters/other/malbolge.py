r"""Interpreter for Malbolge.

Malbolge is a self-modifying machine of 59049 ten-trit words: three registers
``a``/``c``/``d``, a deciphered opcode, and an instruction that is re-enciphered
after every execution.  ``i`` and ``j`` move the pointers, ``*`` rotates and
``p`` applies the crazy operation to memory, ``<`` prints and ``/`` reads, ``o``
is a nop and ``v`` halts.

The reference interpreter hangs forever when the cell at ``c`` leaves 33-126;
this one halts instead, the behaviour the wiki attributes to the specification.
An input character is one line's first character -- the package's line-delimited
convention, where an empty line is 0 -- and EOF is the value 59048, not an
error.  A source character that does not decipher to an instruction raises
:class:`ValueError`.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

#: Instruction decipherment: ``(cell - 33 + c) % 94`` indexes this.
_XLAT1 = (
    '+b(29e*j1VMEKLyC})8&m#~W>qxdRp0wkrUo[D7,XTcA"lI'
    ".v%{gJh4G\\-=O@5`_3i<?Z';FNQuY]szf$!BS/|t:Pn6^Ha"
)
#: Encipherment applied to the cell at ``c`` after each instruction runs.
_XLAT2 = (
    "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1C"
    "B6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
)
#: The crazy operation on two base-9 di-trits, indexed ``[y][x]``.
_CRAZY = (
    (4, 3, 3, 1, 0, 0, 1, 0, 0),
    (4, 3, 5, 1, 0, 2, 1, 0, 2),
    (5, 5, 4, 2, 2, 1, 2, 2, 1),
    (4, 3, 3, 1, 0, 0, 7, 6, 6),
    (4, 3, 5, 1, 0, 2, 7, 6, 8),
    (5, 5, 4, 2, 2, 1, 8, 8, 7),
    (7, 6, 6, 7, 6, 6, 4, 3, 3),
    (7, 6, 8, 7, 6, 8, 4, 3, 5),
    (8, 8, 7, 8, 8, 7, 5, 5, 4),
)
_WORDS = 3**10
_ROTATE = 3**9
_EOF = _WORDS - 1
type _State = tuple[int, int, int, bool]
type _Effect = int | None


def _crazy(x: int, y: int) -> int:
    """Return the crazy operation on ``x`` and ``y``, five di-trits wide."""
    result, place = 0, 1
    for _ in range(5):
        result += _CRAZY[(y // place) % 9][(x // place) % 9] * place
        place *= 9
    return result


def _op(cell: int, c: int) -> str | None:
    """Return the decoded instruction character, or ``None`` to halt."""
    if not 33 <= cell <= 126:
        return None
    return _XLAT1[(cell - 33 + c) % 94]


def _advance(
    state: _State,
    memory: Sequence[int],
    char_input: int | None = None,
) -> tuple[_State, tuple[tuple[int, int], ...], _Effect]:
    """Return the next state, the cells this step writes, and any output.

    ``memory`` is read, never written: the shell applies the returned writes,
    because 59049 cells cannot be copied into an immutable state per step.
    """
    a, c, d, halted = state
    if halted:
        return state, (), None
    cell = memory[c]
    op = _op(cell, c)
    if op is None:
        return (a, c, d, True), (), None
    writes: dict[int, int] = {}
    effect = None

    def peek(address: int) -> int:
        return writes.get(address, memory[address])

    if op == "j":
        d = memory[d]
    elif op == "i":
        c = memory[d]
    elif op == "*":
        value = memory[d]
        a = writes[d] = value // 3 + value % 3 * _ROTATE
    elif op == "p":
        a = writes[d] = _crazy(a, memory[d])
    elif op == "<":
        effect = a & 0xFF
    elif op == "/":
        a = _EOF if char_input is None else char_input
    elif op == "v":
        return (a, c, d, True), (), None
    value = peek(c)
    if 33 <= value <= 126:
        writes[c] = ord(_XLAT2[value - 33])
    c = (c + 1) % _WORDS
    d = (d + 1) % _WORDS
    return (a, c, d, False), tuple(writes.items()), effect


@lru_cache(maxsize=16)
def _initial_memory(code: str) -> tuple[int, ...]:
    """Return reusable initial memory for ``code``."""
    memory = [0] * _WORDS
    index = 0
    for char in code:
        if char.isspace():
            continue
        cell = ord(char)
        # 59049 cells each deciphering to an instruction cannot be built: the
        # decipherment cycles with the cell index, so the decode check below
        # rejects a long source before this can fire.
        if index >= _WORDS:  # pragma: no cover
            raise ValueError("Malbolge program is longer than its 59049 cells")
        decoded = _op(cell, index)
        if decoded is None or decoded not in "ji*p</vo":
            raise ValueError(
                f"Malbolge source character {char!r} at cell {index} does not "
                f"decipher to an instruction"
            )
        memory[index] = cell
        index += 1
    while index < _WORDS:
        memory[index] = _crazy(memory[index - 1], memory[index - 2])
        index += 1
    return tuple(memory)


def _load(code: str) -> list[int]:
    """Return fresh 59049-word memory for ``code``."""
    return list(_initial_memory(code))


class _Machine:
    """Protocol shell holding the registers and the mutable word store."""

    #: EOF is a value here, so an underfed program answers a different row.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.memory = _load(code)
        self.io = io
        self.state: _State = (0, 0, 0, False)

    @property
    def halted(self) -> bool:
        return self.state[3]

    #: The position is a ternary memory address that shares space with data,
    #: not a place in the source a caller can mark.
    ip_shape = "opaque"

    @property
    def ip(self) -> int | None:
        return None if self.halted else self.state[1]

    @property
    def stack(self) -> list[object]:
        return []

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, tuple(self.memory), self.io.position())

    def step(self) -> None:
        if self.halted:
            return
        c = self.state[1]
        char_input = None
        if _op(self.memory[c], c) == "/":
            try:
                char_input = self.io.input_char()
            except EOFError:
                char_input = _EOF
        self.state, writes, effect = _advance(self.state, self.memory, char_input)
        for address, value in writes:
            self.memory[address] = value
        if effect is not None:
            self.io.print_char(chr(effect))


def run(code: str, io: IO) -> None:
    """Execute a Malbolge program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
