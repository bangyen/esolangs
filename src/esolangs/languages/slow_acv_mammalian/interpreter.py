"""Interpreter for SLOW ACV MAMMALIAN.

Whitespace-delimited uppercase commands over 23 arrays, a pointer picking the
current one, and an accumulator.  SEED/CONFLAGRATE operate on all 23 arrays,
EXCRETE/CONSUME/FISSION/DIGEST on the current one, SPRINT moves the pointer,
LEAPFROG jumps, ACCEPT reads a byte, PRONOUNCE prints the accumulator as a
byte.  SPRINT with a too-large ``x`` is a NOP (per the wiki).  Cell
operations and I/O each accept modulus 255 or 256.

Input/output:
    ACCEPT reads one byte; PRONOUNCE writes the accumulator as a byte.

Errors:
    ProgramError: Unknown command word.
    InputExhaustedError: ACCEPT at EOF.
    ArgumentError: A ``cell_modulus`` or ``io_modulus`` setting other than
        255 or 256, or a ``leapfrog_resume`` setting other than ``after``
        or ``at``.

Decisions:
    * LEAPFROG "jump[s] to the (x - first value in array)th instruction"
      counting from 1: the page does not say whether execution resumes at
      that instruction or after it, so the two readings are a registered
      dialect, ``leapfrog_resume`` -- ``after`` (the default; the shipped
      behaviour before the dialect existed) or ``at``.  A count of 0 or
      past the end halts under both.  Generated programs cannot tell the
      readings apart, in every dialect: each jump target is preceded by
      a SPRINT that the jump's accumulator -- a token address, beyond
      every array's length -- makes a no-op.
    * SEED skips an empty array and CONSUME, FISSION and LEAPFROG ignore one.
    * A CONFLAGRATE pair with a zero divisor is left alone.
    * Cells default to modulus 256 ("any value from 0-255"), I/O to 255 (the
      page says EXCRETE and PRONOUNCE are "modulo 255").
"""

from collections.abc import Mapping
from itertools import chain
from typing import Any, NamedTuple

from esolangs.languages.slow_acv_mammalian.dialect import ARRAYS as _ARRAYS
from esolangs.languages.slow_acv_mammalian.dialect import (
    DEFAULT_MODULI,
    MammalianModuli,
)
from esolangs.languages.slow_acv_mammalian.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import keyword_hint, syntax_error

#: One instant of a run: ``(arrays, ptr, acc, ind, halted)`` -- the 23
#: arrays, the pointer that picks the current one, the accumulator, the
#: token cursor, and whether a negative LEAPFROG stopped the run.  A value
#: the transitions below map forward, never editing one in place, with the
#: arrays as nested ``tuple``s for the same reason.
#:
#: ``halted`` is carried because a negative LEAPFROG stops the run with the
#: cursor left where it was, so the position alone does not say.
#:
#: The token stream is not here: it is fixed for the whole run, so a step
#: takes the opcode it is executing as an argument instead.
type _Arrays = tuple[tuple[int, ...], ...]
type _State = tuple[_Arrays, int, int, int, bool]


def _total(
    op: int, arrays: _Arrays, cell_modulus: int = DEFAULT_MODULI.cell_modulus
) -> _Arrays:
    """Return ``arrays`` after SEED (``op == 0``) or CONFLAGRATE.

    SEED adds each array's one-based index to its head mod 256.
    CONFLAGRATE flattens all 23, walks from both ends, and cuts back to the
    original lengths; its asymmetric pairing (the larger side loses
    ``x // y`` unwrapped, the smaller gains ``y % x``) can leave ``0..255``
    and reproducing that is the point.
    """
    if not op:
        # Spelled as a loop rather than the genexpr this reads as, because
        # SEED is the whole cost of a run: the boolean example runs it 1317
        # times, and a generator suspends and resumes once per array, so
        # the comprehension spent 42% of the run in 31608 frame
        # resumptions -- more than the arithmetic it was carrying.  The
        # arrays are 23 short tuples, so building the list directly is the
        # same work without the frames.
        seeded = []
        for num, arr in enumerate(arrays):
            seeded.append(((arr[0] + num + 1) % cell_modulus, *arr[1:]) if arr else arr)
        return tuple(seeded)

    size = [len(arr) for arr in arrays]
    flat = list(chain.from_iterable(arrays))
    m = len(flat)

    for k in range(m // 2):
        x, y = flat[k], flat[m - k - 1]
        n = m - k - 1

        if x > y and y:
            num = x // y
            flat[k] -= num
            flat[n] = (y + num) % cell_modulus
        elif x < y and x:
            num = y % x
            flat[k] += num
            flat[n] -= num

    out: list[tuple[int, ...]] = []
    for k in range(_ARRAYS):
        out.append(tuple(flat[: size[k]]))
        flat = flat[size[k] :]
    return tuple(out)


def _partial(
    op: int,
    curr: tuple[int, ...],
    acc: int,
    io_modulus: int = DEFAULT_MODULI.io_modulus,
) -> tuple[tuple[int, ...], int]:
    """Return the current array and accumulator after one array op.

    EXCRETE (2) appends the accumulator as a byte and clears it, CONSUME (3)
    pops the middle cell (``(len - 1) // 2``), FISSION (4) halves it onto
    both ends, DIGEST folds with XOR.  CONSUME and FISSION on an empty array
    leave the state alone.
    """
    if op == 2:
        return ((*curr, acc % io_modulus), 0)
    if op == 3:
        if not curr:
            return (curr, acc)
        m = (len(curr) - 1) // 2
        return ((*curr[:m], *curr[m + 1 :]), curr[m])
    if op == 4:
        if not curr:
            return (curr, acc)
        m = (len(curr) - 1) // 2
        num = curr[m] // 2
        return ((num, *curr[:m], *curr[m + 1 :], num), acc)
    return (curr, acc ^ sum(curr))


_INS = (
    "SEED",
    "CONFLAGRATE",
    "EXCRETE",
    "CONSUME",
    "FISSION",
    "DIGEST",
    "SPRINT",
    "LEAPFROG",
    "ACCEPT",
    "PRONOUNCE",
)

# Token -> opcode, so a step names its instruction by lookup.
_OPCODE = {name: op for op, name in enumerate(_INS)}


def _tokens(code: str) -> tuple[str, ...]:
    """Return whitespace-delimited instructions; reject unknown words."""
    words = tuple(code.split())
    for word in words:
        if word not in _OPCODE:
            raise syntax_error(
                f"unknown SLOW ACV MAMMALIAN command {word!r}",
                keyword_hint(
                    word, _INS, "use uppercase, whitespace-delimited commands"
                ),
            )
    return words


def _advance(
    state: _State,
    n: int,
    byte: int | None = None,
    *,
    moduli: MammalianModuli = DEFAULT_MODULI,
) -> _State:
    """Return the state after executing the token with opcode ``n``.

    Pure; PRONOUNCE changes only the cursor and ACCEPT's byte arrives as
    ``byte``.  Two positional rules from the original are required: SPRINT's
    guard ``acc < len(curr)`` passes a negative accumulator, which then
    indexes from the far end; LEAPFROG jumps to ``acc - head - 1`` and then
    takes the trailing advance, so the cursor ends at ``target + 1`` --
    under ``leapfrog_resume="at"`` it lands one token earlier, so the
    cursor ends at the target instruction itself.
    """
    arrays, ptr, acc, ind, halted = state
    curr = arrays[ptr]

    if n < 2:
        arrays = _total(n, arrays, moduli.cell_modulus)
    elif n < 6:
        curr, acc = _partial(n, curr, acc, moduli.io_modulus)
        arrays = (*arrays[:ptr], curr, *arrays[ptr + 1 :])
    elif n == 6 and acc < len(curr):
        if acc < -len(curr):
            # The array is a tuple here, so its own subscript would say
            # "tuple index out of range"; a run that walked off the end
            # said "list" before and callers see the message, so keep it.
            raise IndexError("list index out of range")
        ptr = (ptr + curr[acc]) % _ARRAYS
    elif n == 7 and curr and curr[-1]:
        target = acc - curr[0] - 1
        if target < 0:
            return (arrays, ptr, acc, ind, True)
        ind = target if moduli.leapfrog_resume == "after" else target - 1
    elif n == 8 and byte is not None:
        head = (*arrays[0], (byte ^ acc) % moduli.cell_modulus)
        arrays = (head, *arrays[1:])

    return (arrays, ptr, acc, ind + 1, halted)


_WORKSPACE_MODEL = WorkspaceModel(
    "slow-acv-mammalian-v1",
    ("instruction", "arrays", "pointer", "accumulator", "input_cursor", "stopped"),
)


class _Image(NamedTuple):
    moduli: MammalianModuli
    tokens: tuple[str, ...]


def _prepare_source(
    code: str, *, cell_modulus: int, io_modulus: int, leapfrog_resume: str
) -> _Image:
    moduli = MammalianModuli(cell_modulus, io_modulus, leapfrog_resume)
    return _Image(moduli, _tokens(code))


class _Machine:
    """One SLOW ACV MAMMALIAN run: the 23 arrays, pointer, acc, and cursor."""

    def __init__(
        self,
        code: str | _Image,
        io: IO,
        *,
        cell_modulus: int = DEFAULT_MODULI.cell_modulus,
        io_modulus: int = DEFAULT_MODULI.io_modulus,
        leapfrog_resume: str = DEFAULT_MODULI.leapfrog_resume,
    ) -> None:
        image = (
            _prepare_source(
                code,
                cell_modulus=cell_modulus,
                io_modulus=io_modulus,
                leapfrog_resume=leapfrog_resume,
            )
            if isinstance(code, str)
            else code
        )
        self.moduli, self.tokens = image
        self.io = io
        self.lst: _Arrays = tuple((0,) for _ in range(_ARRAYS))
        self.ind = self.ptr = self.acc = 0
        self._halted_by_command = False

    @property
    def halted(self) -> bool:
        """Whether a negative LEAPFROG fired or the cursor reached the end."""
        return self._halted_by_command or self.ind >= len(self.tokens)

    # The VM's language-shaped view: 23 arrays + pointer; memory is the current array,
    # stack all 23.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.lst[self.ptr])

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return [row for arr in self.lst for row in arr]

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        return _WORKSPACE_MODEL.capture(
            instruction=self.ind,
            arrays=tuple(tuple(array) for array in self.lst),
            pointer=self.ptr,
            accumulator=self.acc,
            input_cursor=self.io.progress(),
            stopped=self._halted_by_command,
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.lst,
            self.ptr,
            self.acc,
            self.io.progress(),
            self._halted_by_command,
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transitions work on."""
        return (
            self.lst,
            self.ptr,
            self.acc,
            self.ind,
            self._halted_by_command,
        )

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        self.lst, self.ptr, self.acc, self.ind, self._halted_by_command = state

    def step(self) -> None:
        """Execute one token, advancing (or jumping) the cursor."""
        if self.halted:
            return
        n = _OPCODE[self.tokens[self.ind]]

        byte = None
        if n == 8:
            byte = self.io.input_char()
        elif n == 9:
            self.io.print_char(chr(self.acc % self.moduli.io_modulus))

        self._restore(_advance(self._state, n, byte, moduli=self.moduli))


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain validated commands and dialect for each invocation."""
    if not isinstance(source, str):
        raise TypeError("slow_acv_mammalian machines require text source")
    if options.keys() - {"cell_modulus", "io_modulus", "leapfrog_resume"}:
        raise TypeError("Mammalian machines accept only declared dialect options")
    image = _prepare_source(
        source,
        cell_modulus=options.get("cell_modulus", DEFAULT_MODULI.cell_modulus),
        io_modulus=options.get("io_modulus", DEFAULT_MODULI.io_modulus),
        leapfrog_resume=options.get("leapfrog_resume", DEFAULT_MODULI.leapfrog_resume),
    )
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(
    code: str | _Image,
    io: IO,
    *,
    cell_modulus: int = DEFAULT_MODULI.cell_modulus,
    io_modulus: int = DEFAULT_MODULI.io_modulus,
    leapfrog_resume: str = DEFAULT_MODULI.leapfrog_resume,
) -> CompletionReport:
    """Run with separate cell and EXCRETE/PRONOUNCE moduli, and a resume reading."""
    return drive(
        _Machine(
            code,
            io,
            cell_modulus=cell_modulus,
            io_modulus=io_modulus,
            leapfrog_resume=leapfrog_resume,
        ),
        policy=CAPABILITIES.completion,
    )


def run(
    code: str,
    io: IO,
    *,
    cell_modulus: int = DEFAULT_MODULI.cell_modulus,
    io_modulus: int = DEFAULT_MODULI.io_modulus,
    leapfrog_resume: str = DEFAULT_MODULI.leapfrog_resume,
) -> None:
    """Run with separate cell and EXCRETE/PRONOUNCE moduli, and a resume reading."""
    _execute(
        code,
        io,
        cell_modulus=cell_modulus,
        io_modulus=io_modulus,
        leapfrog_resume=leapfrog_resume,
    )


if __name__ == "__main__":
    script_main(run)
