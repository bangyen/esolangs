"""Run one Flowchart tick over pointers, deques and buffered bits."""

from bisect import bisect_left
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import assert_never

from esolangs.languages.flowchart._diagram import (
    _EXITS,
    _accepts,
    _anchor,
    _exits_from_node,
    _forward_first,
    _Spelling,
    _turn_left,
    _turn_right,
)
from esolangs.runtime.source_hints import syntax_error


class _Memory:
    """Where a pointer last left each cell it has been through.

    A map, not a tuple of pairs: a tuple scanned on read and rebuilt on
    record, both in Python, so a pointer through Theta(T) cells paid
    Theta(T) per step.

    Still a value.  Nothing mutates after construction, so a fork may share
    one freely; a record returns a new memory (a ``dict`` copy done in C),
    which lets two generations be compared and a loop be proved.  The
    pointer is never hashed; :meth:`_Pointer.state` builds the hashable view
    the cycle detector compares.  This is hashable anyway, since that is
    cheap and a value ought to be.
    """

    __slots__ = ("_digest", "_exits", "_sorted")

    def __init__(self, exits: dict[tuple[int, int], tuple[int, int]]) -> None:
        """Take ownership of ``exits``; callers must not keep a reference."""
        self._exits = exits
        self._digest: int | None = None
        self._sorted: tuple[tuple[object, ...], ...] | None = None

    def exit_from(self, cell: tuple[int, int]) -> tuple[int, int] | None:
        """Return the heading this pointer last left ``cell`` on."""
        return self._exits.get(cell)

    def leaving(self, cell: tuple[int, int], d: tuple[int, int]) -> "_Memory":
        """Return this memory with ``cell``'s exit heading recorded."""
        if self._exits.get(cell) == d:
            return self
        exits = dict(self._exits)
        exits[cell] = d
        memory = _Memory(exits)
        items = self.sorted_items()
        index = bisect_left(items, (cell,))
        stop = index + int(index < len(items) and items[index][0] == cell)
        memory._sorted = (*items[:index], (cell, d), *items[stop:])
        return memory

    def sorted_items(self) -> tuple[tuple[object, ...], ...]:
        """Return the exits in a fixed order, for the snapshot."""
        if self._sorted is None:
            self._sorted = tuple(sorted(self._exits.items()))
        return self._sorted

    def __eq__(self, other: object) -> bool:
        """Memories are equal when they record the same exits."""
        if not isinstance(other, _Memory):
            return NotImplemented
        return self._exits == other._exits

    def __hash__(self) -> int:
        """Hash the exits, computed once -- a memory never changes."""
        if self._digest is None:
            self._digest = hash(frozenset(self._exits.items()))
        return self._digest


@dataclass(frozen=True)
class _Pointer:
    """One program pointer: a position, a heading, a register, a cursor.

    ``row``/``col`` is the cell the pointer currently occupies, ``d`` the
    heading it is travelling on, ``reg`` its own register (``None`` when
    empty), and ``deque`` its index into the shared tape of deques.  A
    pointer that has reached an ``(( ))`` is ``done``.

    Frozen: a step returns the pointers that follow rather than editing its
    arguments.  ``replace`` builds the changed copy; ``memory`` is a
    :class:`_Memory`, itself a value, so a fork shares one.
    """

    row: int
    col: int
    d: tuple[int, int]
    reg: int | None = None
    deque: int = 0
    done: bool = False
    # The cell stepped away from, so a multi-cell node knows which of its
    # neighbours the pointer entered through.
    prev: tuple[int, int] | None = None
    # Where this pointer last left each node or path cell.  The spec makes
    # re-entry a property of the pointer ("a node or path *it's* been
    # through"), so each carries its own; a node's entry is keyed by its
    # anchor cell, not by whichever column the pointer stood on.
    memory: _Memory = field(default_factory=lambda: _Memory({}))

    def remembered(self, cell: tuple[int, int]) -> tuple[int, int] | None:
        """Return the heading this pointer last left ``cell`` on."""
        return self.memory.exit_from(cell)

    def remembering(self, cell: tuple[int, int], d: tuple[int, int]) -> "_Pointer":
        """Return this pointer with ``cell``'s exit heading recorded."""
        return replace(self, memory=self.memory.leaving(cell, d))

    def state(self) -> tuple[object, ...]:
        """Return this pointer's state, hashable for cycle detection."""
        return (
            self.row,
            self.col,
            self.d,
            self.reg,
            self.deque,
            self.done,
            self.prev,
            self.memory.sorted_items(),
        )


@dataclass(frozen=True)
class _Run:
    """The whole of a Flowchart run the pure transition owns.

    The grid and parsed nodes are fixed for a run; these are the values a
    tick changes: every live pointer, the shared deques, and the output
    byte a partial write is gathering.  Frozen, so a step returns a new
    run rather than editing the one it was handed.
    """

    pointers: tuple[_Pointer, ...]
    deques: Mapping[int, tuple[int | None, ...]]
    outgoing: int = 0
    used: int = 0


class _NeedBitError(Exception):
    """Ask the shell for one more input bit a transition has run out of.

    Carries ``printed``: the output bytes the tick had already produced when
    it reached the read, so the shell can flush that prefix *before* it
    performs the read and keep the original event order.
    """

    def __init__(self, printed: tuple[int, ...]) -> None:
        super().__init__("the tick needs another input bit")
        self.printed = printed


def _remembered(
    p: _Pointer,
    nodes: Mapping[tuple[int, int], tuple[_Spelling, int]],
    row: int,
    col: int,
    allowed: list[tuple[int, int]],
) -> tuple[int, int] | None:
    """Return ``p``'s remembered exit from ``(row, col)``, if it may be taken.

    The spec declines the remembered direction when following it would
    turn the pointer 180 degrees, so a rail that re-enters a cell head-on
    falls back to the ordinary rules instead.
    """
    d = p.remembered(_anchor(nodes, row, col))
    if d is None or d not in allowed:
        return None
    if d == (-p.d[0], -p.d[1]):
        # The spec's 180-degree decline.
        return None  # pragma: no cover - no known grid reaches it
    return d


def _advance(
    run: _Run,
    grid: tuple[str, ...],
    nodes: Mapping[tuple[int, int], tuple[_Spelling, int]],
    width: int,
    bits: Sequence[int | None],
) -> tuple[_Run, tuple[int, ...]]:
    """Run one node per live pointer, returning the next run and output bytes.

    Pure: input arrives as ``bits`` and output is returned, not written.  A
    bit a ``/ /`` node still needs is raised as :class:`_NeedBitError` for
    the shell to answer, carrying the bytes written before the read; any
    other fault carries the same prefix on its ``printed`` attribute, so the
    shell can flush it before the read or the rethrow.
    """
    printed: list[int] = []
    try:
        return _Tick(run, grid, nodes, width, bits, printed).advance()
    except _NeedBitError:
        raise
    except BaseException as fault:
        fault.printed = tuple(printed)  # type: ignore[attr-defined]
        raise


class _Tick:
    """Scratch for one tick: copies of the run's state, edited in place."""

    def __init__(
        self,
        run: _Run,
        grid: tuple[str, ...],
        nodes: Mapping[tuple[int, int], tuple[_Spelling, int]],
        width: int,
        bits: Sequence[int | None],
        printed: list[int],
    ) -> None:
        self.run = run
        self.grid = grid
        self.nodes = nodes
        self.width = width
        self.bits = bits
        self.printed = printed
        self.pointers = list(run.pointers)
        self.deques = dict(run.deques)
        self.outgoing = run.outgoing
        self.used = run.used
        self.pos = 0

    def read_bit(self) -> int | None:
        """Return the next supplied bit, or ask the shell for one."""
        if self.pos >= len(self.bits):
            raise _NeedBitError(tuple(self.printed))
        bit = self.bits[self.pos]
        self.pos += 1
        return bit

    def write_bit(self, bit: int) -> None:
        self.outgoing |= bit << self.used
        self.used += 1
        if self.used == 8:
            self.printed.append(self.outgoing)
            self.outgoing = self.used = 0

    def move(self, i: int, d: tuple[int, int]) -> None:
        p = self.pointers[i]
        n_row, n_col = p.row + d[0], p.col + d[1]
        if not _accepts(self.grid, self.nodes, self.width, n_row, n_col, d):
            self.pointers[i] = replace(p, done=True)
            return
        self.pointers[i] = replace(p, prev=(p.row, p.col), row=n_row, col=n_col, d=d)

    def follow_path(self, i: int) -> None:
        p = self.pointers[i]
        c = self.grid[p.row][p.col]
        back = (-p.d[0], -p.d[1])
        allowed = [d for d in _EXITS.get(c, ()) if d != back]
        if not allowed:  # pragma: no cover - no line character has a single arm
            self.pointers[i] = replace(p, done=True)
            return
        if len(allowed) > 1:
            remembered = _remembered(p, self.nodes, p.row, p.col, allowed)
            if remembered is not None:
                allowed = [remembered]
            elif p.d in allowed:
                allowed = [p.d]
        d = next(d for d in (p.d, _turn_right(p.d), _turn_left(p.d)) if d in allowed)
        self.pointers[i] = p.remembering(_anchor(self.nodes, p.row, p.col), d)
        self.move(i, d)

    def ride(self, i: int) -> None:
        seen: set[tuple[int, int, tuple[int, int]]] = set()
        p = self.pointers[i]
        while not p.done and (p.row, p.col) not in self.nodes:
            if (p.row, p.col, p.d) in seen:
                return
            seen.add((p.row, p.col, p.d))
            self.follow_path(i)
            p = self.pointers[i]

    def step_to(self, i: int, row: int, col: int, d: tuple[int, int]) -> None:
        p = self.pointers[i]
        p = p.remembering(_anchor(self.nodes, p.row, p.col), d)
        self.pointers[i] = replace(p, prev=(p.row, p.col), row=row, col=col, d=d)

    def exits(self, p: _Pointer) -> list[tuple[int, int, tuple[int, int]]]:
        """Return the paths out of ``p``'s node; a non-end node must have one."""
        exits = _exits_from_node(
            self.grid, self.nodes, self.width, p.row, p.col, p.prev
        )
        if not exits:
            raise syntax_error(
                "non-end node has no exit path",
                "connect an exit path or use an end node",
            )
        return exits

    def leave(self, i: int, prefer: tuple[int, int] | None = None) -> None:
        p = self.pointers[i]
        exits = self.exits(p)
        order = (p.d, _turn_right(p.d), _turn_left(p.d))
        exits.sort(key=lambda step: order.index(step[2]))
        if prefer is None and len(exits) > 1:
            prefer = _remembered(p, self.nodes, p.row, p.col, [d for _, _, d in exits])
        selected = next((exit_ for exit_ in exits if exit_[2] == prefer), exits[0])
        self.step_to(i, *selected)

    def fork(self, i: int) -> None:
        p = self.pointers[i]
        exits = _forward_first(self.exits(p), p.d)
        here = (p.row, p.col)
        for n_row, n_col, d in exits[1:]:
            self.pointers.append(
                _Pointer(n_row, n_col, d, p.reg, p.deque, prev=here, memory=p.memory)
            )
        n_row, n_col, d = exits[0]
        self.step_to(i, n_row, n_col, d)

    def switch(self, i: int) -> None:
        p = self.pointers[i]
        if p.reg is None:
            self.leave(i, p.d)
            return
        prefer = _turn_left(p.d) if p.reg == 1 else _turn_right(p.d)
        if not any(d == prefer for _, _, d in self.exits(p)):
            prefer = p.d
        self.leave(i, prefer)

    def operate(self, spelling: _Spelling, p: _Pointer) -> _Pointer:
        """Apply a register, deque or IO node to ``p``; return the updated pointer."""
        reg, deque = p.reg, p.deque
        deques = self.deques
        if spelling == "[ ]":
            reg = 1 if reg is None else reg ^ 1
        elif spelling == "{ ]":
            reg = 0
        elif spelling == "[ }":
            reg = 1
        elif spelling == "{ }":
            reg = None
        elif spelling == "/ /":
            reg = self.read_bit()
        elif spelling == "\\ \\":
            self.write_bit(reg or 0)
        elif spelling == "\\[ ]/":
            deques[p.deque] = (*deques.get(p.deque, ()), reg)
        elif spelling == "/[ ]\\":
            deques[p.deque] = (reg, *deques.get(p.deque, ()))
        elif spelling == "\\{ }/":
            cells = deques.get(p.deque, ())
            reg = cells[-1] if cells else None
            deques[p.deque] = cells[:-1]
        elif spelling == "/{ }\\":
            cells = deques.get(p.deque, ())
            reg = cells[0] if cells else None
            deques[p.deque] = cells[1:]
        elif spelling == "< ]":
            deque -= 1
        elif spelling == "[ >":
            deque += 1
        elif (
            spelling == "(( ))" or spelling == "( )" or spelling == "< >"
        ):  # pragma: no cover
            raise AssertionError("control nodes are dispatched by execute")
        else:
            # Unreachable, and checked to be: ``_Spelling`` is exhausted by
            # the arms above, so mypy narrows this to ``Never``.
            assert_never(spelling)
        return replace(p, reg=reg, deque=deque)

    def execute(self, i: int) -> None:
        p = self.pointers[i]
        spelling = self.nodes[(p.row, p.col)][0]
        if spelling == "(( ))":
            self.pointers[i] = replace(p, done=True)
        elif spelling == "( )":
            self.fork(i)
        elif spelling == "< >":
            self.switch(i)
        else:
            self.pointers[i] = self.operate(spelling, p)
            self.leave(i)

    def ready(self, live: list[int]) -> list[int]:
        """Return the ``live`` pointers resting on a node, in execution order."""
        at = self.pointers
        ready = [
            i for i in live if not at[i].done and (at[i].row, at[i].col) in self.nodes
        ]
        ready.sort(key=lambda i: (at[i].row, self.nodes[(at[i].row, at[i].col)][1], i))
        return ready

    def advance(self) -> tuple[_Run, tuple[int, ...]]:
        """Run every live pointer to its node and execute them; return the new run."""
        if all(p.done for p in self.pointers):
            return self.run, ()
        live = [i for i, p in enumerate(self.pointers) if not p.done]
        for i in live:
            self.ride(i)
        for i in self.ready(live):
            self.execute(i)
        if self.used and all(p.done for p in self.pointers):
            self.printed.append(self.outgoing)
            self.outgoing = self.used = 0
        run = _Run(
            tuple(self.pointers),
            MappingProxyType(self.deques),
            self.outgoing,
            self.used,
        )
        return run, tuple(self.printed)
