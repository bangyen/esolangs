r"""Interpreter for AddSubJump (ASJ)."""

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_int_memory as _parse

# The largest memory a run will.
# list backing them is not:.
# would satisfy, so the run.
# spending the box's memory.
_MAX_MEMORY = 1 << 24

_IO = -1
_CF, _ZF, _NF, _VF = -2, -3, -4, -5
_ONE, _ZERO, _NEG = -6, -7, -8
_FUM = -9
_SPECIAL = set(range(_FUM, _IO + 1))


# : One instant of a run:.
# : self-modifying store, the.
# : flag-update mode.
# : a new one rather than.
#: write for the same reason.
# :.
# : The memory is in the state.
# : rewrites it as it runs.
# : the store, and ``halted``.
#: length.
# :.
# : It is *sparse* --.
# : addresses a program uses.
# : writing cell 999999.
# : zero.
# : what ``halted`` and the.
# : off the container.
# : is what freezes it for the.
type _Cells = tuple[dict[int, int], int]
type _State = tuple[_Cells, int, int, int, int, int, int]


def _pack(values: list[int]) -> _Cells:
    r"""Return ``values`` as the sparse store: non-zero cells, and the."""
    return ({i: v for i, v in enumerate(values) if v}, len(values))


def _operands(state: _State) -> tuple[int, int, int, int]:
    r"""Return the four cells of the instruction under the pointer."""
    (cells, length), ip = state[0], state[1]
    return (
        cells.get(ip, 0),
        cells.get(ip + 1, 0) if ip + 1 < length else 0,
        cells.get(ip + 2, 0) if ip + 2 < length else 0,
        cells.get(ip + 3, 0) if ip + 3 < length else 0,
    )


def _load(state: _State, addr: int, byte: int | None = None) -> int:
    r"""Return the value at ``addr``, which may be a special register."""
    (cells, length), _ip, cf, zf, nf, vf, fum = state
    if addr == _IO:
        return byte if byte is not None else 0
    if addr == _CF:
        return cf
    if addr == _ZF:
        return zf
    if addr == _NF:
        return nf
    if addr == _VF:
        return vf
    if addr == _ONE:
        return 1
    if addr == _ZERO:
        return 0
    if addr == _NEG:
        return -1
    if addr == _FUM:
        return fum
    return cells.get(addr, 0) if 0 <= addr < length else 0


def _too_large(state: _State, addr: int) -> bool:
    r"""Whether writing ``addr`` would grow the store past what is allowed."""
    _cells, length = state[0]
    return (
        addr != _IO
        and addr not in _SPECIAL
        and addr >= length
        and addr + 1 > _MAX_MEMORY
    )


def _store(state: _State, addr: int, value: int) -> _State:
    r"""Return ``state`` with ``addr`` set to ``value``."""
    (cells, length), ip, cf, zf, nf, vf, fum = state
    if addr == _IO:
        return state
    if addr in _SPECIAL:
        return (state[0], ip, cf, zf, nf, vf, value) if addr == _FUM else state
    if addr >= length:
        length = addr + 1
    new = dict(cells)
    if value:
        new[addr] = value
    else:
        new.pop(addr, None)
    return ((new, length), ip, cf, zf, nf, vf, fum)


def _advance(state: _State, reads: tuple[int, ...]) -> tuple[int, _State]:
    r"""Return the value the instruction computed, and the state after it."""
    pending = list(reads)

    def take(addr: int) -> int:
        return _load(state, addr, pending.pop(0) if addr == _IO else None)

    a, b, c, d = _operands(state)
    vd = take(d)
    vb = take(b)
    if a == _IO:
        value = vb
    else:
        va = take(a)
        value = va - vb if vd > 0 else va + vb

    after = _store(state, a, value)
    memory, _ip, cf, zf, nf, vf, fum = after
    if fum:
        zf = 1 if value == 0 else 0
        nf = 1 if value < 0 else 0
        cf = vf = 0
    after = (memory, _ip, cf, zf, nf, vf, fum)
    return value, (memory, _load(after, c), cf, zf, nf, vf, fum)


class _Machine:
    r"""Per-run ASJ state: the self-modifying memory, ip, and flags."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Parse ``code`` into memory and reset the pointer and flags."""
        self.io = io
        self.state: _State = (_pack(list(_parse(code))), 0, 0, 0, 0, 0, 0)

    # The language's own names.
    # than fields of their own, so.

    @property
    def memory(self) -> list[int]:
        r"""The self-modifying store, densified."""
        cells, length = self.state[0]
        return [cells.get(i, 0) for i in range(length)]

    @property
    def ip(self) -> int:
        r"""The instruction pointer."""
        return self.state[1]

    @property
    def cf(self) -> int:
        return self.state[2]

    @property
    def zf(self) -> int:
        return self.state[3]

    @property
    def nf(self) -> int:
        return self.state[4]

    @property
    def vf(self) -> int:
        r"""The Overflow flag (``VF``, address -5)."""
        return self.state[5]

    @property
    def fum(self) -> int:
        r"""Whether the flags follow each instruction's result."""
        return self.state[6]

    @property
    def halted(self) -> bool:
        r"""Whether the pointer is off the end of memory or a special address."""
        (_cells, length), ip = self.state[0], self.state[1]
        return ip < 0 or ip >= length

    # The VM's language-shaped.
    # pointer.
    # the empty stack needs saying.

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The state as it stands plus.
        # ignores consumed input is not.
        # .
        # The sparse store's dict is.
        # follows insertion, so equal.
        # orders would freeze.
        # the key depend on the.
        # than a frozenset because a.
        # processes, which the mutation.
        (cells, length) = self.state[0]
        return (
            tuple(sorted(cells.items())),
            length,
            *self.state[1:],
            self.io.position(),
        )

    def step(self) -> None:
        r"""Execute one instruction, advancing the pointer."""
        if self.halted:
            return
        a, b, _c, d = _operands(self.state)
        if _too_large(self.state, a):
            raise HaltError(f"memory address {a} is too large")
        reads = tuple(
            self.io.input_char()
            for addr in ((d, b) if a == _IO else (d, b, a))
            if addr == _IO
        )
        value, self.state = _advance(self.state, reads)
        if a == _IO:
            self.io.print_char(chr(value & 0xFF))


def run(code: str, io: IO) -> None:
    r"""Run an AddSubJump program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
