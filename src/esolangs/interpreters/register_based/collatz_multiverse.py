r"""Interpreter for Collatz Multiverse."""

from __future__ import annotations

import re
import sys
from typing import cast

from esolangs.interpreters.io import IO

# : The registers, as an.
type _Regs = tuple[tuple[str, int], ...]

# : The arrays, as an immutable.
type _Arrays = tuple[tuple[str, tuple[tuple[int, int], ...]], ...]

# : One instant of a run:.
# : the two stores.
# : new one rather than editing.
# :.
# : Both stores are sorted by.
# : one logical store has.
# : frozensets from these, as.
# : same cells in different.
# :.
# : The parsed program is.
# : during a run, so carrying.
# : cycle detector stores.
#: transition instead.
type _State = tuple[int, _Regs, _Arrays]


def _reg_get(regs: _Regs, name: str) -> int:
    r"""Return the value of ``name``, or zero for a register never written."""
    for key, value in regs:
        if key == name:
            return value
    return 0


def _reg_set(regs: _Regs, name: str, value: int) -> _Regs:
    r"""Return ``regs`` with ``name`` set to ``value``, in name order."""
    kept = tuple((k, v) for k, v in regs if k != name)
    return tuple(sorted((*kept, (name, value))))


def _arr_get(arrays: _Arrays, name: str, index: int) -> int:
    r"""Return ``name[index]``, or zero for a cell never written."""
    for key, cells in arrays:
        if key == name:
            for i, value in cells:
                if i == index:
                    return value
            return 0
    return 0


def _arr_set(arrays: _Arrays, name: str, index: int, value: int) -> _Arrays:
    r"""Return ``arrays`` with ``name[index]`` set, in name and index order."""
    cells: tuple[tuple[int, int], ...] = ()
    for key, existing in arrays:
        if key == name:
            cells = existing
            break
    kept = tuple((i, v) for i, v in cells if i != index)
    updated = tuple(sorted((*kept, (index, value))))
    others = tuple((k, v) for k, v in arrays if k != name)
    return tuple(sorted((*others, (name, updated))))


_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_LINE = re.compile(
    rf"^\s*({_NAME})(?:\[({_NAME})\])?\s*=\s*"
    rf"({_NAME})(?:\[({_NAME})\])?\s*x\s*\+\s*"
    rf"({_NAME})(?:\[({_NAME})\])?\s*,\s*(DO|NOT)\s+PRINT\.\s*$"
)


class _Machine:
    r"""Per-run Collatz Multiverse state: registers, arrays, and the."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Parse ``code`` into lines and start at line 1."""
        self.io = io
        lines = [ln for ln in code.splitlines() if ln.strip()]
        self.n = len(lines)
        self.parsed: list[_Line] = []
        for ln in lines:
            m = _LINE.fullmatch(ln)
            if not m:
                raise ValueError(f"malformed line: {ln!r}")
            # Redefining ``input`` is.
            # property of the program text.
            # the other two malformed cases.
            # happens to run.
            # unreachable ``input =`` line.
            # legal, and made acceptance.
            # target can be read from input.
            if m.group(1) == "input":
                raise ValueError("input cannot be redefined")
            self.parsed.append(cast("_Line", m.groups()))
        # ``negativeOne`` starts at -1;.
        self.state: _State = (1, (("negativeOne", -1),), ())

    # The language's own names.
    # than fields of their own, so.

    @property
    def ip(self) -> int:
        r"""The current line, 1-indexed."""
        return self.state[0]

    @property
    def registers(self) -> dict[str, int]:
        r"""The named registers."""
        return dict(self.state[1])

    @property
    def arrays(self) -> dict[str, dict[int, int]]:
        r"""The arrays, by name."""
        return {name: dict(cells) for name, cells in self.state[2]}

    @property
    def halted(self) -> bool:
        r"""Whether the pointer has left the program."""
        return not (1 <= self.state[0] <= self.n)

    # The VM's language-shaped.
    # memory the regs.

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        # The registers are kept in.
        return [value for _name, value in self.state[1]]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # Frozensets, as this always.
        # already canonically ordered.
        ip, regs, arrays = self.state
        return (
            frozenset(regs),
            frozenset((name, frozenset(cells)) for name, cells in arrays),
            ip,
            self.io.position(),
        )

    def step(self) -> None:
        r"""Execute one line, moving the pointer."""
        if self.halted:
            return
        line = self.parsed[self.state[0] - 1]
        var1, idx1, var2, idx2, var3, idx3, do_print = line
        # The three operand slots are.
        # read before the array it.
        # recursion produced.
        reads = []
        for name, index in ((var1, idx1), (var2, idx2), (var3, idx3)):
            if index == "input":
                reads.append(self.io.input_num())
            if name == "input":
                reads.append(self.io.input_num())
        value, self.state = _advance(self.state, line, tuple(reads))
        if do_print == "DO":
            self.io.print_char(chr(value & 0xFF))


# : One operand as parsed: a.
# : subscript.
# : numeric literals -- so an.
type _Operand = tuple[str, str | None]

# : One parsed line: the three.
# : in the order the regex.
type _Line = tuple[str, str | None, str, str | None, str, str | None, str]


def _plain(state: _State, name: str) -> int:
    r"""Read a non-indexed, non-input operand."""
    ip, regs, _arrays = state
    return ip if name == "lineNumber" else _reg_get(regs, name)


def _operand(state: _State, spec: _Operand, pending: list[int]) -> int:
    r"""Read one operand, taking any ``input`` value the shell pre-read."""
    name, index = spec
    idx = 0
    if index == "input":
        idx = pending.pop(0)
    elif index is not None:
        idx = _plain(state, index)
    if name == "input":
        return pending.pop(0)
    if name == "lineNumber":
        return state[0]
    if index is not None:
        return _arr_get(state[2], name, idx)
    return _reg_get(state[1], name)


def _advance(
    state: _State,
    line: _Line,
    reads: tuple[int, ...],
) -> tuple[int, _State]:
    r"""Return the computed value and the state after executing one line."""
    ip, regs, arrays = state
    var1, idx1, var2, idx2, var3, idx3, _do_print = line
    pending = list(reads)

    target = _operand(state, (var1, idx1), pending)
    a = _operand(state, (var2, idx2), pending)
    b = _operand(state, (var3, idx3), pending)
    value = target * a + b if target == 0 or target % 2 != 0 else target // 2

    next_ip = ip + 1
    if var1 == "lineNumber":
        next_ip = value
    elif idx1 is not None:
        arrays = _arr_set(arrays, var1, _plain(state, idx1), value)
    else:
        regs = _reg_set(regs, var1, value)
    return value, (next_ip, regs, arrays)


def run(code: str, io: IO) -> None:
    r"""Run a Collatz Multiverse program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
