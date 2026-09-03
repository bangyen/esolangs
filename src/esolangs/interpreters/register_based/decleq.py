"""Interpreter for Decleq.

An OISC whose instruction ``a b c`` means ``b = a - 1`` and jumps to ``c``
if the new ``b`` is less than or equal to zero.  The program is a
self-modifying memory: the source file is a list of integers (whitespace-
separated, ``#`` comments allowed), the instruction pointer starts at 0, and
the instruction at address ``pc`` is the three cells
``memory[pc]..memory[pc+2]``, so the common countdown idiom is ``x x next``
(decrement ``x``, jump to ``next`` when it reaches zero).

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state to the next state, and never mutates what it
is given.  It takes no ``io`` argument at all, so it is total and
side-effect free by construction rather than by inspection.

The memory is a ``tuple``, so a state is a value that can be stored,
compared, and hashed as it stands.  That the memory *grows* is the reason
it has to be in the state rather than alongside it: writing past the end
extends it, and ``halted`` is defined by the pointer against the current
length, so the length is part of what a step decides -- not a fixed
property of the program.  A snapshot that dropped it would call two
genuinely different situations the same.

:class:`_Machine` is the mutable shell the interpreter protocol requires
(``esolangs.vm`` wraps it, and ``run_until_halt_or_cycle`` steps it to
prove a hang where it can).  It holds one ``_State`` and rebinds it each
step, so the mutation lives in exactly one assignment and every rule about
what Decleq *does* stays in the pure layer.  The two memory-mapped I/O
opcodes are the one place an effect happens, and ``step`` does them before
calling the pure transition -- effects in the shell, rules in the core.

Documented decisions for gaps in the wiki stub:
- ``a b c`` stores ``memory[a] - 1`` into ``memory[b]`` (the literal reading
  of "b = a - 1"; with ``a == b`` it is a plain decrement), then jumps to
  ``c`` when ``memory[b] <= 0`` and otherwise falls through three cells;
- the optional memory-mapped I/O is implemented: ``a = -2`` outputs
  ``memory[b]`` as a byte, ``a = -1`` reads a byte of input into
  ``memory[b]``, and both fall through rather than jump;
- cells are unbounded integers, and the pointer halts when it moves off
  the end of memory; exhausted input raises :class:`EOFError` (repo-wide
  convention).

Malformed programs raise :class:`ValueError`.

There is no per-run instruction cap here.  A self-decrementing cell (``a b
c`` with ``a == b`` and a positive start value, jumping to itself) never
revisits a snapshot -- verified by construction: ``memory[b]`` walks down
by exactly one every pass, so the state the cycle detector hashes is new
every time, forever, on unbounded integers.  ``run_until_halt_or_cycle``
provably cannot terminate on that program, which is exactly the class
``esolangs.run``'s wall-clock ``timeout`` exists for; a step count local to
this interpreter would only have duplicated it.
"""

from __future__ import annotations

from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_int_memory as _parse

_OUT = -2
_IN = -1

#: One instant of a run: ``(pc, memory)`` -- the program counter and the
#: self-modifying store.  A value, not a record: every transition below
#: returns a new one rather than editing one in place, and the memory is a
#: ``tuple`` for the same reason.
#:
#: The memory is in the state rather than beside it because this language
#: rewrites it as it runs *and* can extend it: a write past the end grows
#: the store, and ``halted`` compares the pointer against the current
#: length.  The length is therefore something a step decides, and two states
#: that agree on every cell they share but not on how many cells exist are
#: different states.
#:
#: A plain tuple rather than a ``NamedTuple``: the fields are read by
#: unpacking in the functions that use them, so the names bought little, and
#: ``NamedTuple.__new__`` is Python-level where the tuple constructor is
#: C-level.
type _State = tuple[int, tuple[int, ...]]


def _read(memory: tuple[int, ...], addr: int) -> int:
    """Return ``memory[addr]``, or zero when the address is out of range.

    Reading off either end is not an error -- the wiki's programs rely on
    untouched addresses behaving as zero -- so the bounds check lives here
    once rather than at each of the three call sites.
    """
    return memory[addr] if 0 <= addr < len(memory) else 0


def _written(memory: tuple[int, ...], addr: int, value: int) -> tuple[int, ...]:
    """Return ``memory`` with cell ``addr`` set to ``value``, growing if needed.

    A write past the *right* end extends the store with zeros up to
    ``addr``, which is what makes the length part of the state: the same
    program text can reach different lengths depending on what it has
    written.

    A negative ``addr`` indexes from the right, as a write through Python's
    own subscript did before the store became a tuple -- ``-1`` is the last
    cell.  That is not a nicety: the transpiler fuzz relies on such a write
    landing somewhere real (or raising on an empty store) rather than
    growing the store, and growing instead turns a terminating program into
    a non-terminating one.
    """
    if addr < 0:
        # IndexError on an empty or too-short store, exactly as a list
        # subscript would raise, which callers above treat as a real error.
        if addr < -len(memory):
            raise IndexError("list assignment index out of range")
        addr += len(memory)
    elif addr >= len(memory):
        memory = (*memory, *([0] * (addr + 1 - len(memory))))
    return (*memory[:addr], value, *memory[addr + 1 :])


def _operands(state: _State) -> tuple[int, int, int]:
    """Return the three cells of the instruction under the pointer.

    A trailing instruction that runs off the end of memory reads its
    missing operands as zero, the same rule :func:`_read` applies to any
    out-of-range address.
    """
    pc, memory = state
    return (memory[pc], _read(memory, pc + 1), _read(memory, pc + 2))


def _advance(state: _State, byte: int | None = None) -> _State:
    """Return the state after executing the instruction under the pointer.

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so the two memory-mapped I/O opcodes are necessarily the
    caller's business; this function sees only what they leave behind --
    ``-2``'s output changes no state beyond the pointer, and ``-1``'s byte
    arrives as ``byte``, already read.

    Both I/O opcodes fall through three cells rather than jumping.  The
    ordinary instruction is the only one that branches, and it branches on
    the value it just wrote, not the one it read.
    """
    pc, memory = state
    a, b, c = _operands(state)
    if a == _OUT:
        return (pc + 3, memory)
    if a == _IN:
        # ``byte`` is what the shell read; the write can grow the store.
        return (pc + 3, _written(memory, b, byte if byte is not None else 0))
    value = _read(memory, a) - 1
    memory = _written(memory, b, value)
    return (c if value <= 0 else pc + 3, memory)


class _Machine:
    """A Decleq run: one immutable ``_State``, rebound per step.

    The protocol the rest of the library expects (``step``, ``halted``,
    ``snapshot``, and the ``memory``/``pc`` attributes) is mutable by
    construction, so this class supplies it.  All it does is hold the
    current state; the rules themselves are the pure functions above.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into memory and reset the pointer."""
        self.io = io
        self.state: _State = (0, tuple(_parse(code)))

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def pc(self) -> int:
        return self.state[0]

    @pc.setter
    def pc(self, value: int) -> None:
        # Writable so a caller can place the pointer directly on a state
        # that running the program cannot reach cleanly -- the truncated
        # tail below cell 6 is only reachable past a cell that has since
        # become the input opcode.
        self.state = (value, self.state[1])

    @property
    def halted(self) -> bool:
        """Whether the pointer has moved off the end of memory."""
        pc, memory = self.state
        return pc < 0 or pc >= len(memory)

    # The VM's language-shaped view: OISC cells + program counter.

    @property
    def ip(self) -> int:
        """The program counter."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        # A list, because that is what this exposed before the memory became
        # a tuple, and the VM copies what it is handed.
        return list(self.state[1])

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The memory is already a tuple, so it goes in as it stands.  The
        # input cursor joins it because a repeat that ignores consumed input
        # is not a real cycle.
        pc, memory = self.state
        return (memory, pc, self.io.position())

    def step(self) -> None:
        """Execute one instruction, advancing the pointer.

        The two memory-mapped I/O opcodes are done here rather than in a
        function of their own: this is the shell, so it is where an effect
        belongs, and it keeps :func:`_advance` reachable in one call per
        step.  ``-2`` writes and changes no memory; ``-1`` reads and hands
        the byte to the transition, which stores it.
        """
        if self.halted:
            return
        a, b, _c = _operands(self.state)
        byte = None
        if a == _OUT:
            self.io.print_char(chr(_read(self.state[1], b) & 0xFF))
        elif a == _IN:
            byte = self.io.input_char()
        self.state = _advance(self.state, byte)


def run(code: str, io: IO) -> None:
    """Run a Decleq program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
