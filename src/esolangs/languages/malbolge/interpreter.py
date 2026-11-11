r"""Interpreter for Malbolge.

Malbolge is a self-modifying machine of 59049 ten-trit words: three registers
``a``/``c``/``d``, a deciphered opcode, and an instruction that is re-enciphered
after every execution.  ``i`` and ``j`` move the pointers, ``*`` rotates and
``p`` applies the crazy operation to memory, ``<`` prints and ``/`` reads, ``o``
is a nop and ``v`` halts.  The run halts when the cell at ``c`` leaves 33-126.

Input/output:
    Input consumes consecutive Unicode characters, including newlines.  EOF is
    the value 59048, not an error.

Errors:
    ProgramError: A source character that does not decipher to an instruction.

Decisions:
    * The reference interpreter hangs forever when the cell at ``c`` leaves
      33-126; this one halts instead, the behaviour the wiki attributes to the
      specification.
    * When ``i`` lands ``c`` on such a cell, the cell is left as it is rather
      than encrypted: the spec's table has no entry for it (the reference
      indexes outside its array), and the next instruction runs at ``c + 1``.
    * The spec does not define input encoding or framing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

from esolangs.languages.malbolge.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO
from esolangs.runtime.persistent import CHUNK, Chunked, chunked
from esolangs.runtime.source_hints import syntax_error

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
_ENCRYPT = tuple(map(ord, _XLAT2))

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
#: The commands that act; ``o`` is the no-op the loader also admits.
_ACTIVE_OPS = "ji*p</v"
_NOP = "o"
type _State = tuple[int, int, int, bool]
type _Effect = int | None


def _crazy(x: int, y: int) -> int:
    """Return the crazy operation on ``x`` and ``y``, five di-trits wide."""
    return (
        _CRAZY[(y // 1) % 9][(x // 1) % 9] * 1
        + _CRAZY[(y // 9) % 9][(x // 9) % 9] * 9
        + _CRAZY[(y // 81) % 9][(x // 81) % 9] * 81
        + _CRAZY[(y // 729) % 9][(x // 729) % 9] * 729
        + _CRAZY[(y // 6561) % 9][(x // 6561) % 9] * 6561
    )


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
    if op not in _ACTIVE_OPS:
        # Native n=12 controls take 12.8M transitions, mostly no-ops.
        # Their sole write needs neither a scratch dictionary nor a peek closure.
        return (
            (a, (c + 1) % _WORDS, (d + 1) % _WORDS, False),
            ((c, _ENCRYPT[cell - 33]),),
            None,
        )
    writes: dict[int, int] = {}
    effect = None

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
    value = writes.get(c, memory[c])
    if 33 <= value <= 126:
        writes[c] = _ENCRYPT[value - 33]
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
            raise syntax_error(
                "Malbolge program is longer than its 59049 cells",
                "keep the source within 59049 memory cells",
            )
        decoded = _op(cell, index)
        if decoded is None or decoded not in _ACTIVE_OPS + _NOP:
            raise syntax_error(
                f"Malbolge source character {char!r} at cell {index} does not "
                f"decipher to an instruction",
                (
                    "choose printable source characters whose "
                    "position-dependent decoding is a Malbolge instruction"
                ),
            )
        memory[index] = cell
        index += 1
    while index < _WORDS:
        memory[index] = _crazy(memory[index - 1], memory[index - 2])
        index += 1
    return tuple(memory)


# Canonical pages avoid the flat-copy formula sweep exceeding 60 s, without
# depending on the cycle cache partition.
_WORKSPACE_PAGE = 64
_WORKSPACE_MODEL = WorkspaceModel(
    "malbolge-v1",
    ("accumulator", "instruction", "data", "stopped", "memory", "input_cursor"),
)


type _Image = tuple[tuple[int, ...], Chunked[int]]


def _prepare_source(code: str) -> _Image:
    memory = _initial_memory(code)
    return memory, chunked(memory)


class _Machine:
    """Protocol shell holding the registers and the mutable word store."""

    #: EOF is a value here, so an underfed program answers a different row.
    eof_is_a_value = True

    def __init__(self, code: str | _Image, io: IO) -> None:
        memory, chunks = _prepare_source(code) if isinstance(code, str) else code
        self.memory = list(memory)
        self.io = io
        self.state: _State = (0, 0, 0, False)
        # ``snapshot``'s memory as fixed chunks, rebuilt only where a step
        # wrote: an untouched chunk stays the same object between snapshots,
        # so a per-step snapshot costs the writes, not all 59049 words.
        self._chunks = list(chunks)
        self._dirty: set[int] = set()
        self._workspace_pages: list[tuple[int, ...]] | None = None
        self._workspace_dirty: set[int] = set()

    @property
    def halted(self) -> bool:
        return self.state[3]

    #: The position is a ternary memory address that shares space with data,
    #: not a place in the source a caller can mark.
    ip_shape = "opaque"

    @property
    def ip(self) -> int | None:
        return None if self.halted else self.state[1]

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture the finite word store independently of cycle-cache chunks."""
        if self._workspace_pages is None:
            self._workspace_pages = [
                tuple(self.memory[start : min(start + _WORKSPACE_PAGE, _WORDS)])
                for start in range(0, _WORDS, _WORKSPACE_PAGE)
            ]
        for page in self._workspace_dirty:
            start = page * _WORKSPACE_PAGE
            self._workspace_pages[page] = tuple(
                self.memory[start : min(start + _WORKSPACE_PAGE, _WORDS)]
            )
        self._workspace_dirty.clear()
        a, c, d, halted = self.state
        return _WORKSPACE_MODEL.capture(
            accumulator=a,
            instruction=c,
            data=d,
            stopped=halted,
            memory=tuple(self._workspace_pages),
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        for at in self._dirty:
            self._chunks[at] = tuple(self.memory[at * CHUNK : (at + 1) * CHUNK])
        self._dirty.clear()
        return (*self.state, tuple(self._chunks), self.io.progress())

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
            self._dirty.add(address // CHUNK)
            if self._workspace_pages is not None:
                self._workspace_dirty.add(address // _WORKSPACE_PAGE)
        if effect is not None:
            self.io.print_char(chr(effect))


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the immutable initial image and bind fresh memory per run."""
    if not isinstance(source, str):
        raise TypeError("malbolge machines require text source")
    if options:
        raise TypeError("malbolge machines accept no runtime options")
    image = _prepare_source(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _Image, io: IO) -> CompletionReport:
    """Execute a Malbolge program."""
    machine = _Machine(code, io)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Execute a Malbolge program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
