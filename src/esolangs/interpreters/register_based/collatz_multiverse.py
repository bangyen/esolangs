"""Interpreter for Collatz Multiverse.

Every line is ``[var1] = [var2] x + [var3], [DO|NOT] PRINT.``: an odd or
zero var1 becomes ``var1 * var2 + var3``, an even one is halved, and
``DO`` prints the low byte.  Variables start at 0; ``arr[var]`` indexes
(bare ``arr`` is ``arr[0]``); ``negativeOne`` starts at -1; ``input``
reads an integer and cannot be a target; ``lineNumber`` is the 1-based
current line and assigning it jumps (the Collatz rule applies to it
too).  Non-blank lines are numbered from 1; the run halts when the
pointer leaves.  var2/var3 and indices must be names (the wiki rejects
``var = 3 x + 1``); ``input`` raises :class:`EOFError` when exhausted; a
malformed line, numeric literal or redefinition of ``input`` raises
:class:`ValueError`.  :func:`_advance` is pure over an immutable
``_State``; the shell pre-reads every ``input`` a line names, and
:func:`_read` defaults a missing array to zero rather than creating it.
"""

from __future__ import annotations

import re
from typing import cast

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

#: The registers, as an immutable name->value mapping.
type _Regs = tuple[tuple[str, int], ...]

#: The arrays, as an immutable name->(index->value) mapping.
type _Arrays = tuple[tuple[str, tuple[tuple[int, int], ...]], ...]

#: One instant of a run: ``(ip, registers, arrays)`` -- the line pointer and
#: the two stores.  A value, not a record: every transition below returns a
#: new one rather than editing one in place.
#:
#: Both stores are sorted by name (and arrays by index within a name), so
#: one logical store has exactly one spelling.  ``snapshot`` builds
#: frozensets from these, as it always did, and two runs that wrote the
#: same cells in different orders must hash alike.
#:
#: The parsed program is deliberately not in here.  It does not change
#: during a run, so carrying it would put constant data in every value the
#: cycle detector stores.  The current line is a parameter to the
#: transition instead.
type _State = tuple[int, _Regs, _Arrays]


def _reg_get(regs: _Regs, name: str) -> int:
    """Return the value of ``name``, or zero for a register never written."""
    for key, value in regs:
        if key == name:
            return value
    return 0


def _reg_set(regs: _Regs, name: str, value: int) -> _Regs:
    """Return ``regs`` with ``name`` set to ``value``, in name order."""
    kept = tuple((k, v) for k, v in regs if k != name)
    return tuple(sorted((*kept, (name, value))))


def _arr_get(arrays: _Arrays, name: str, index: int) -> int:
    """Return ``name[index]``, or zero for a cell never written."""
    for key, cells in arrays:
        if key == name:
            for i, value in cells:
                if i == index:
                    return value
            return 0
    return 0


def _arr_set(arrays: _Arrays, name: str, index: int, value: int) -> _Arrays:
    """Return ``arrays`` with ``name[index]`` set, in name and index order."""
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
    """Per-run Collatz Multiverse state: registers, arrays, and the pointer."""

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into lines and start at line 1."""
        self.io = io
        lines = [ln for ln in code.splitlines() if ln.strip()]
        self.n = len(lines)
        self.parsed: list[_Line] = []
        for ln in lines:
            m = _LINE.fullmatch(ln)
            if not m:
                raise ValueError(f"malformed line: {ln!r}")
            # Redefining ``input`` is malformed, and malformedness is a
            # property of the program text -- so it is rejected here with
            # the other two malformed cases rather than when the line
            # happens to run.  Checking it in ``step()`` made an
            # unreachable ``input =`` line (one a ``lineNumber`` jump skips)
            # legal, and made acceptance depend on stdin, since a jump
            # target can be read from input.
            if m.group(1) == "input":
                raise ValueError("input cannot be redefined")
            self.parsed.append(cast("_Line", m.groups()))
        # ``negativeOne`` starts at -1; every other name starts at 0.
        self.state: _State = (1, (("negativeOne", -1),), ())

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ip(self) -> int:
        """The current line, 1-indexed."""
        return self.state[0]

    @property
    def registers(self) -> dict[str, int]:
        """The named registers."""
        return dict(self.state[1])

    @property
    def arrays(self) -> dict[str, dict[int, int]]:
        """The arrays, by name."""
        return {name: dict(cells) for name, cells in self.state[2]}

    @property
    def halted(self) -> bool:
        """Whether the pointer has left the program."""
        return not (1 <= self.state[0] <= self.n)

    # The VM's language-shaped view: Named registers + line pointer; ip the line,
    # memory the regs.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        # The registers are kept in name order, so this is already sorted.
        return [value for _name, value in self.state[1]]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Frozensets, as this always returned, built from stores that are
        # already canonically ordered.
        ip, regs, arrays = self.state
        return (
            frozenset(regs),
            frozenset((name, frozenset(cells)) for name, cells in arrays),
            ip,
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one line, moving the pointer.

        Every ``input`` the line names (up to three) is read here, in the
        transition's order.
        """
        if self.halted:
            return
        line = self.parsed[self.state[0] - 1]
        var1, idx1, var2, idx2, var3, idx3, do_print = line
        # The three operand slots are read left to right, and an index is
        # read before the array it indexes -- the order the old _read
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


#: One operand as parsed: a name, and the index name when it is an array
#: subscript.  Both halves are plain identifiers -- the language rejects
#: numeric literals -- so an index is always another variable to look up.
type _Operand = tuple[str, str | None]

#: One parsed line: the three operand name/index pairs and the print flag,
#: in the order the regex captures them.
type _Line = tuple[str, str | None, str, str | None, str, str | None, str]


def _plain(state: _State, name: str) -> int:
    """Read a non-indexed, non-input operand (index operands come here too)."""
    ip, regs, _arrays = state
    return ip if name == "lineNumber" else _reg_get(regs, name)


def _operand(state: _State, spec: _Operand, pending: list[int]) -> tuple[int, int]:
    """Read one operand and its resolved array index.

    ``pending`` is consumed in operand order: index before its name, left to right.
    """
    name, index = spec
    idx = 0
    if index == "input":
        idx = pending.pop(0)
    elif index is not None:
        idx = _plain(state, index)
    if name == "input":
        return pending.pop(0), idx
    if name == "lineNumber":
        return state[0], idx
    if index is not None:
        return _arr_get(state[2], name, idx), idx
    return _reg_get(state[1], name), idx


def _advance(
    state: _State,
    line: _Line,
    reads: tuple[int, ...],
) -> tuple[int, _State]:
    """Return the computed value and the state after executing one line.

    The value comes back because ``DO PRINT`` is the shell's.  ``reads``
    holds the pre-read ``input`` values.
    """
    ip, regs, arrays = state
    var1, idx1, var2, idx2, var3, idx3, _do_print = line
    pending = list(reads)

    target, target_index = _operand(state, (var1, idx1), pending)
    a, _ = _operand(state, (var2, idx2), pending)
    b, _ = _operand(state, (var3, idx3), pending)
    value = target * a + b if target == 0 or target % 2 != 0 else target // 2

    next_ip = ip + 1
    if var1 == "lineNumber":
        next_ip = value
    elif idx1 is not None:
        arrays = _arr_set(arrays, var1, target_index, value)
    else:
        regs = _reg_set(regs, var1, value)
    return value, (next_ip, regs, arrays)


def run(code: str, io: IO) -> None:
    """Run a Collatz Multiverse program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
