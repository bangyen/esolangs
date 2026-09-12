r"""Interpreter for Flowchart."""

import sys
from dataclasses import dataclass, replace
from typing import Literal, assert_never

from esolangs.interpreters.io import IO

# Headings, as (d_row, d_col).
_UP = (-1, 0)
_DOWN = (1, 0)
_LEFT = (0, -1)
_RIGHT = (0, 1)
_HEADINGS = (_RIGHT, _DOWN, _LEFT, _UP)

# The spellings, as a type.
# and it copies out of.
# dispatches on is one of these.
# that mypy narrows to the last.
# Adding a node means adding it.
# stops type-checking.
_Spelling = Literal[
    "(( ))",
    "\\[ ]/",
    "/[ ]\\",
    "\\{ }/",
    "/{ }\\",
    "( )",
    "[ ]",
    "{ ]",
    "[ }",
    "{ }",
    "< >",
    "/ /",
    "\\ \\",
    "< ]",
    "[ >",
]

# Node spellings, longest.
# ``[ >`` and ``[ ]`` share a.
# matched inside a longer one.
_NODES: tuple[_Spelling, ...] = (
    "(( ))",
    "\\[ ]/",
    "/[ ]\\",
    "\\{ }/",
    "/{ }\\",
    "( )",
    "[ ]",
    "{ ]",
    "[ }",
    "{ }",
    "< >",
    "/ /",
    "\\ \\",
    "< ]",
    "[ >",
)

# Characters that carry a.
# plain conduit: the headings.
_EXITS = {
    "─": (_LEFT, _RIGHT),
    "│": (_UP, _DOWN),
    "┌": (_RIGHT, _DOWN),
    "┐": (_LEFT, _DOWN),
    "└": (_RIGHT, _UP),
    "┘": (_LEFT, _UP),
    "┬": (_LEFT, _RIGHT, _DOWN),
    "┴": (_LEFT, _RIGHT, _UP),
    "├": (_UP, _DOWN, _RIGHT),
    "┤": (_UP, _DOWN, _LEFT),
    "┼": (_LEFT, _RIGHT, _UP, _DOWN),
}


def _turn_left(d: tuple[int, int]) -> tuple[int, int]:
    r"""Return the heading 90 degrees to the left of ``d``."""
    d_row, d_col = d
    return (-d_col, d_row)


def _turn_right(d: tuple[int, int]) -> tuple[int, int]:
    r"""Return the heading 90 degrees to the right of ``d``."""
    d_row, d_col = d
    return (d_col, -d_row)


@dataclass(frozen=True)
class _Pointer:
    r"""One program pointer: a position, a heading, a register, a cursor."""

    row: int
    col: int
    d: tuple[int, int]
    reg: int | None = None
    deque: int = 0
    done: bool = False
    # The cell stepped away from,.
    # neighbours the pointer.
    prev: tuple[int, int] | None = None
    # Where this pointer last left.
    # re-entry a property of the.
    # through"), so each carries.
    # anchor cell, not by whichever.
    memory: tuple[tuple[tuple[int, int], tuple[int, int]], ...] = ()

    def remembered(self, cell: tuple[int, int]) -> tuple[int, int] | None:
        r"""Return the heading this pointer last left ``cell`` on."""
        for key, value in self.memory:
            if key == cell:
                return value
        return None

    def remembering(self, cell: tuple[int, int], d: tuple[int, int]) -> "_Pointer":
        r"""Return this pointer with ``cell``'s exit heading recorded."""
        kept = tuple((k, v) for k, v in self.memory if k != cell)
        return replace(self, memory=(*kept, (cell, d)))

    def state(self) -> tuple[object, ...]:
        r"""Return this pointer's state, hashable for cycle detection."""
        return (
            self.row,
            self.col,
            self.d,
            self.reg,
            self.deque,
            self.done,
            self.prev,
            tuple(sorted(self.memory)),
        )


@dataclass
class _State:
    r"""Every mutable value in a Flowchart run."""

    pointers: list[_Pointer]
    deques: dict[int, list[int]]


class _Machine:
    r"""Per-run Flowchart state: the grid, its pointers, and the deques."""

    # : Whether a read past the end.
    # : rather than raising.
    # :.
    # : package norm and what.
    # : not, so an underfed program.
    # : instead of refusing, and a.
    #: that it happened.
    # :.
    # : Declared rather than.
    # : audited against every wiki.
    # : (``docs/limitations.md``,.
    # : would be a decision about.
    # : What was wrong was that.
    # : was false for seven.
    #: out which.
    eof_is_a_value = True

    def __init__(self, code: list[str], io: IO) -> None:
        r"""Parse ``code``'s nodes and start on the first ``( )``."""
        self.io = io
        rows = [line.rstrip("\n") for line in code]
        self.width = max((len(r) for r in rows), default=0)
        self.grid = tuple(r.ljust(self.width) for r in rows)

        # (row, col) -> (node spelling,.
        # cell a node covers maps to.
        # column of the box executes it.
        self.nodes: dict[tuple[int, int], tuple[_Spelling, int]] = {}
        self._parse()

        start = self._start()
        self.state = _State([_Pointer(start[0], start[1], _RIGHT)], {})
        self._fork_at_start()

    @property
    def pointers(self) -> list[_Pointer]:
        r"""The live pointers, retained as a convenience for step helpers."""
        return self.state.pointers

    @pointers.setter
    def pointers(self, pointers: list[_Pointer]) -> None:
        self.state.pointers = pointers

    @property
    def deques(self) -> dict[int, list[int]]:
        r"""The shared deques, retained as a convenience for step helpers."""
        return self.state.deques

    def _parse(self) -> None:
        r"""Record every node on the grid, longest spelling first."""
        for row, line in enumerate(self.grid):
            col = 0
            while col < len(line):
                for spelling in _NODES:
                    if line.startswith(spelling, col):
                        for i in range(len(spelling)):
                            self.nodes[(row, col + i)] = (spelling, col)
                        col += len(spelling)
                        break
                else:
                    c = line[col]
                    if c != " " and c not in _EXITS:
                        raise ValueError(f"unknown character {c!r} at ({col}, {row})")
                    col += 1
        self._check_alignment()

    def _check_alignment(self) -> None:
        r"""Reject a vertical path that enters a node off its middle."""
        for row, line in enumerate(self.grid):
            for col, c in enumerate(line):
                arms = _EXITS.get(c)
                if arms is None:
                    continue
                for arm in (_UP, _DOWN):
                    if arm not in arms:
                        continue
                    node = self.nodes.get((row + arm[0], col))
                    if node is None:
                        continue
                    spelling, col0 = node
                    middle = col0 + len(spelling) // 2
                    if col != middle:
                        raise ValueError(
                            f"vertical path at ({col}, {row}) enters {spelling!r} at "
                            f"column {col}, but its middle is column {middle}"
                        )

    def _start(self) -> tuple[int, int]:
        r"""Return the top-most, left-most ``( )`` node's first cell."""
        for row in range(len(self.grid)):
            for col in range(self.width):
                node = self.nodes.get((row, col))
                if node and node[0] == "( )" and node[1] == col:
                    return (row, col)
        raise ValueError("Flowchart program has no '( )' start node")

    def _fork_at_start(self) -> None:
        r"""Split the initial pointer if the start node has several exits."""
        p = self.pointers[0]
        here = (p.row, p.col)
        exits = self._reading_order(self._exits_from_node(p.row, p.col, None))
        if not exits:
            self.pointers[0] = replace(p, done=True)
            return
        self.pointers = [_Pointer(row, col, d, prev=here) for row, col, d in exits]

    def _cells_of(self, row: int, col: int) -> list[tuple[int, int]]:
        r"""Return every cell covered by the node at ``(row, col)``."""
        spelling, col0 = self.nodes[(row, col)]
        return [(row, col0 + i) for i in range(len(spelling))]

    @staticmethod
    def _reading_order(
        exits: list[tuple[int, int, tuple[int, int]]],
    ) -> list[tuple[int, int, tuple[int, int]]]:
        r"""Sort a fork's exits top-most first, then left-most."""
        return sorted(exits, key=lambda step: (step[0], step[1]))

    def _anchor(self, row: int, col: int) -> tuple[int, int]:
        r"""Return the key a cell's re-entry memory is stored under."""
        node = self.nodes.get((row, col))
        return (row, node[1]) if node else (row, col)

    def _exits_from_node(
        self, row: int, col: int, came_from: tuple[int, int] | None
    ) -> list[tuple[int, int, tuple[int, int]]]:
        r"""Return the ``(row, col, heading)`` steps leaving the node at."""
        cells = set(self._cells_of(row, col))
        out: list[tuple[int, int, tuple[int, int]]] = []
        seen: set[tuple[int, int]] = set()
        for c_row, c_col in sorted(cells, key=lambda c: (c[0], c[1])):
            for d in _HEADINGS:
                n_row, n_col = c_row + d[0], c_col + d[1]
                if (n_row, n_col) in cells or not self._in_bounds(n_row, n_col):
                    continue
                if (n_row, n_col) == came_from:
                    continue
                if not self._accepts(n_row, n_col, d):
                    continue
                # A node is reached once.
                # box; a bare path cell is its.
                node = self.nodes.get((n_row, n_col))
                target = (n_row, node[1]) if node else (n_row, n_col)
                if target in seen:
                    continue
                seen.add(target)
                out.append((n_row, n_col, d))
        return out

    def _in_bounds(self, row: int, col: int) -> bool:
        r"""Whether ``(row, col)`` is on the grid."""
        return 0 <= row < len(self.grid) and 0 <= col < self.width

    def _accepts(self, row: int, col: int, d: tuple[int, int]) -> bool:
        r"""Whether a pointer may enter ``(row, col)`` travelling on ``d``."""
        if not self._in_bounds(row, col):
            return False
        if (row, col) in self.nodes:
            return True
        c = self.grid[row][col]
        return c in _EXITS and (-d[0], -d[1]) in _EXITS[c]

    @property
    def halted(self) -> bool:
        r"""Whether every pointer has stopped."""
        return all(p.done for p in self.pointers)

    # The VM's language-shaped view.

    # : ``ip`` is a cell of the.
    # : parts are a row and a.
    # : this a caller cannot tell.
    # : stack, which look identical.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...] | None:
        r"""The first pointer still running, or ``None`` once none is."""
        for pointer in self.pointers:
            if not pointer.done:
                return (pointer.row, pointer.col, *pointer.d)
        return None

    @property
    def memory(self) -> list[int]:
        r"""The shared tape of deques, concatenated in index order."""
        return [v for key in sorted(self.deques) for v in self.deques[key]]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(p.state() for p in self.pointers),
            tuple(sorted((k, tuple(v)) for k, v in self.deques.items() if v)),
            self.io.position(),
        )

    def step(self) -> None:
        r"""Advance every live pointer one cell, in creation order."""
        if self.halted:
            return
        for i in range(len(self.pointers)):
            if not self.pointers[i].done:
                self._advance(i)

    def _put(self, i: int, p: _Pointer) -> None:
        r"""Write ``p`` back as the ``i``th pointer."""
        self.pointers[i] = p

    def _advance(self, i: int) -> None:
        r"""Execute the cell under pointer ``i``, then move it one cell on."""
        p = self.pointers[i]
        if (p.row, p.col) in self.nodes:
            self._execute(i)
        else:
            self._follow_path(i)

    def _follow_path(self, i: int) -> None:
        r"""Move pointer ``i`` along the line character it is standing on."""
        p = self.pointers[i]
        c = self.grid[p.row][p.col]
        back = (-p.d[0], -p.d[1])
        allowed = [d for d in _EXITS.get(c, ()) if d != back]
        if not allowed:  # pragma: no cover - no line character has a single arm
            # A pointer only ever stands on.
            # both _move and.
            # always one of this cell's.
            # only for a one-armed.
            # guard stays so adding one.
            self._put(i, replace(p, done=True))
            return
        if len(allowed) > 1:
            remembered = self._remembered(p, p.row, p.col, allowed)
            if remembered is not None:
                allowed = [remembered]
            elif p.d in allowed:
                allowed = [p.d]
        d = allowed[0]
        self._put(i, p.remembering(self._anchor(p.row, p.col), d))
        self._move(i, d)

    def _remembered(
        self, p: _Pointer, row: int, col: int, allowed: list[tuple[int, int]]
    ) -> tuple[int, int] | None:
        r"""Return ``p``'s remembered exit from ``(row, col)``, if it may be."""
        d = p.remembered(self._anchor(row, col))
        if d is None or d not in allowed:
            return None
        if d == (-p.d[0], -p.d[1]):
            # The spec's 180-degree decline.
            # this is not a proof: a.
            # never reached it, but the.
            # examples, so it stays.
            return None  # pragma: no cover - no known grid reaches it
        return d

    def _move(self, i: int, d: tuple[int, int]) -> None:
        r"""Step pointer ``i`` one cell along ``d``, stopping off the grid."""
        p = self.pointers[i]
        n_row, n_col = p.row + d[0], p.col + d[1]
        if not self._accepts(n_row, n_col, d):
            self._put(i, replace(p, done=True))
            return
        self._put(i, replace(p, prev=(p.row, p.col), row=n_row, col=n_col, d=d))

    def _leave(self, i: int, prefer: tuple[int, int] | None = None) -> None:
        r"""Move ``p`` off the node it occupies."""
        p = self.pointers[i]
        exits = self._exits_from_node(p.row, p.col, p.prev)
        if not exits:
            self._put(i, replace(p, done=True))
            return
        if prefer is not None:
            for n_row, n_col, d in exits:
                if d == prefer:
                    self._step_to(i, n_row, n_col, d)
                    return
        if len(exits) > 1:
            remembered = self._remembered(p, p.row, p.col, [d for _, _, d in exits])
            for n_row, n_col, d in exits:
                if d == remembered:
                    self._step_to(i, n_row, n_col, d)
                    return
            for n_row, n_col, d in exits:
                if d == p.d:
                    self._step_to(i, n_row, n_col, d)
                    return
        n_row, n_col, d = exits[0]
        self._step_to(i, n_row, n_col, d)

    def _step_to(self, i: int, row: int, col: int, d: tuple[int, int]) -> None:
        r"""Record the exit taken from the node and move to ``(row, col)``."""
        p = self.pointers[i]
        p = p.remembering(self._anchor(p.row, p.col), d)
        self._put(i, replace(p, prev=(p.row, p.col), row=row, col=col, d=d))

    def _fork(self, i: int) -> None:
        r"""Split pointer ``i`` across every path leaving a ``( )`` node."""
        p = self.pointers[i]
        exits = self._reading_order(self._exits_from_node(p.row, p.col, p.prev))
        if not exits:
            self._put(i, replace(p, done=True))
            return
        here = (p.row, p.col)
        for n_row, n_col, d in exits[1:]:
            self.pointers.append(
                _Pointer(n_row, n_col, d, p.reg, p.deque, prev=here, memory=p.memory)
            )
        n_row, n_col, d = exits[0]
        self._step_to(i, n_row, n_col, d)

    def _deque(self, p: _Pointer) -> list[int]:
        r"""Return ``p``'s currently selected deque, creating it if needed."""
        return self.deques.setdefault(p.deque, [])

    def _execute(self, i: int) -> None:
        r"""Run the node under pointer ``i``, then move it off that node."""
        p = self.pointers[i]
        spelling = self.nodes[(p.row, p.col)][0]

        if spelling == "(( ))":
            self._put(i, replace(p, done=True))
            return
        if spelling == "( )":
            self._fork(i)
            return
        if spelling == "< >":
            self._switch(i)
            return

        reg, deque = p.reg, p.deque
        if spelling == "[ ]":
            reg = 1 if reg is None else reg ^ 1
        elif spelling == "{ ]":
            reg = 0
        elif spelling == "[ }":
            reg = 1
        elif spelling == "{ }":
            reg = None
        elif spelling == "/ /":
            reg = self._read_bit()
        elif spelling == "\\ \\":
            if reg is not None:
                self.io.print_str(str(reg))
        elif spelling == "\\[ ]/":
            if reg is not None:
                self._deque(p).append(reg)
        elif spelling == "/[ ]\\":
            if reg is not None:
                self._deque(p).insert(0, reg)
        elif spelling == "\\{ }/":
            cells = self._deque(p)
            reg = cells.pop() if cells else None
        elif spelling == "/{ }\\":
            cells = self._deque(p)
            reg = cells.pop(0) if cells else None
        elif spelling == "< ]":
            deque -= 1
        elif spelling == "[ >":
            deque += 1
        else:
            # Unreachable, and checked to.
            # the arms above, so mypy.
            # to the type but not.
            # than silently falling through.
            assert_never(spelling)

        self._put(i, replace(p, reg=reg, deque=deque))
        self._leave(i)

    def _switch(self, i: int) -> None:
        r"""Route ``p`` by its register: 1 turns left, 0 right, empty goes on."""
        p = self.pointers[i]
        if p.reg is None:
            self._leave(i, p.d)
            return
        prefer = _turn_left(p.d) if p.reg == 1 else _turn_right(p.d)
        exits = self._exits_from_node(p.row, p.col, p.prev)
        if not any(d == prefer for _, _, d in exits):
            prefer = p.d
        self._leave(i, prefer)

    def _read_bit(self) -> int | None:
        r"""Read one bit of input, or ``None`` once the input is exhausted."""
        try:
            value = self.io.input_str()
        except (EOFError, IndexError):
            return None
        return 1 if value.strip() == "1" else 0


def run(code: list[str], io: IO) -> None:
    r"""Execute a Flowchart program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
