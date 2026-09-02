r"""Interpreter for Flowchart.

Nodes drawn as literal flowchart boxes are joined by box-drawing lines, and
one or more pointers walk those lines, executing the node they land on.
Each pointer owns a register holding a single bit (``0``, ``1``, or empty)
and a cursor into a shared, infinite tape of deques; the deques themselves
are shared by every pointer.  Execution starts on the top-most, left-most
``( )`` node travelling right, and the program halts once every pointer has
stopped on an ``(( ))``.

The nodes, all of which the wiki (https://esolangs.org/wiki/Flowchart)
tabulates explicitly:

===========  ==================================================
``( )``      start / fork / no-op; the only node that splits
``(( ))``    end; a pointer that reaches it stops
``[ ]``      toggle the register (empty becomes 1)
``{ ]``      set the register to 0
``[ }``      set the register to 1
``{ }``      clear the register, making it empty
``< >``      switch: 1 turns left, 0 turns right, empty goes on
``/ /``      read one bit of input into the register
``\ \``      output the register's bit (nothing when it is empty)
``\[ ]/``    push the register onto the top of the deque
``/[ ]\``    push the register onto the bottom of the deque
``\{ }/``    pop the deque's top into the register
``/{ }\``    pop the deque's bottom into the register
``< ]``      select the previous deque
``[ >``      select the next deque
===========  ==================================================

The spec leaves five things unstated that a running interpreter has to
settle.  Each is resolved below against the wiki's own worked examples
rather than invented, and every one of the three examples on the page
(truth machine, cat, Kolakoski) is exercised by the test suite:

* **A switch's left and right are relative to the pointer's heading**,
  not absolute compass directions.  The truth machine's ``< >`` is entered
  travelling *downward*: register 1 has to reach the ``\ \`` that loops
  back (drawn to the grid-east) and register 0 has to reach the ``\ \``
  and ``(( ))`` that halt (drawn to the grid-west).  Heading-relative
  left/right is the only reading that puts 1 on the looping branch, so the
  example pins the orientation down even though the prose does not.

* **Bits are read and written as characters, not packed into bytes.**  The
  Boolfuck convention buffers eight bits and emits one byte, but
  that convention cannot express Flowchart's own truth machine: given
  ``0`` it reads a single bit, writes a single bit, and halts, so an
  eight-bit output buffer would never flush and the program would print
  nothing at all.  ``/ /`` therefore reads one line and takes ``1`` as a
  one bit and anything else as a zero, and ``\ \`` prints a literal
  ``'0'`` or ``'1'``.  Exhausted input leaves the register empty, which is
  exactly the "empty if there are no more bits to read" the spec asks for.

* **Re-entry memory disambiguates paths; it never suppresses a node.**
  The spec says a pointer re-entering a node or path it has already
  travelled "will go in the direction that it had previously travelled
  unless it were to turn it 180deg".  Read as a rule about *node semantics*
  it would break the wiki's own cat program, whose ``< >`` nodes sit inside
  a loop and must be free to decide differently on each lap -- if the first
  decision were replayed forever the loop could never exit.  So a node's
  own semantics always run, and the remembered direction only settles
  genuine ambiguity: which way to leave a junction (a ``T``-shaped fork in
  the line) or a node whose semantics do not name an exit.  The 180deg
  clause then means the remembered direction is declined whenever taking
  it would reverse the pointer.

* **An empty register produces nothing rather than a zero.**  The spec's
  table says of ``\ \`` that "empty is zero", but the wiki's own cat program
  contradicts the sentence: its read loop ends by popping an exhausted
  deque, so the pointer reaches the output node with an empty register on
  its last lap.  Emitting a zero there would make the cat print a trailing
  ``0`` it never read (``101`` in, ``1010`` out), which is not a cat.  The
  example is taken as ground truth, so ``\ \`` prints nothing on an empty
  register; for the same reason a push of an empty register is a no-op (the
  deques hold bits, and empty is not one) and a pop from an exhausted deque
  leaves the register empty.  The truth machine never outputs an empty
  register, so nothing else on the page constrains this.

  This one is a genuine judgment call and could reasonably go the other
  way.  The page is from 2025 and categorised Unimplemented, so its
  diagrams were almost certainly never run, and a spurious trailing bit is
  exactly the kind of edge case a hand-written example misses -- "the cat
  is simply buggy, and the prose means what it says" is a defensible
  reading.  What tipped it here is that the two are not symmetric: under
  "empty is zero" *every* terminating run of the cat emits the extra bit,
  since its read loop can only end by popping an exhausted deque, so the
  example would not be slightly wrong but categorically not a cat.  The
  page asserts both things and no implementation satisfies both, so
  something on it is wrong either way.  Reverting is small and local:
  print ``"0"`` for an empty register in :meth:`_Machine._execute` and
  update ``test_no_trailing_zero_from_the_empty_register``.

* **Pointers run in lock-step, round-robin, in creation order.**  The
  spec fixes the starting order (top-most, left-most) and says pointers
  "run in parallel" but never gives an interleaving, and because the deques
  are shared the choice is observable.  One step per pointer per round keeps
  the ordering the spec does give, and a fork creates its pointers in the
  reading order of the cells its paths leave through -- top-most first, then
  left-most -- which is the same order the spec uses to pick the starting
  node.  A pointer's deque cursor is likewise unspecified; it is kept
  per-pointer here, alongside the register the spec does make per-pointer.

One further rule the spec does state, and this interpreter enforces:

* **A vertical path enters a node at the node's middle.**  The wiki says
  "vertical paths connecting into a node are expected to connect to the
  middle of the node", and all three worked examples obey it -- 32 vertical
  attachments, every one centred.  It is tempting to read the sentence as a
  drawing convention rather than a law, because those same examples enter
  nodes *horizontally* at their end cells 47 times (the Kolakoski program's
  top row is one long horizontal chain).  But the two are not in tension: a
  node is a contiguous run of cells on a single row, so a horizontal
  neighbour is always at ``col0 - 1`` or ``col0 + len`` and the cell it enters
  is always an end cell.  Horizontal entry cannot be drawn any other way,
  so the spec has nothing to say about it and constrains the one case a
  program can actually get wrong.  Vertical entry off the middle is
  therefore malformed, and :meth:`_Machine._check_alignment` rejects it.

  Note this is a check on *entry*, not on movement: a pointer already
  inside a node still leaves through whichever cell of the box its exit
  sits on, and a rail may still pass a node by without touching it.

Malformed programs (an unknown node, a vertical path meeting a node off its
middle, or no ``( )`` to start from) raise :class:`ValueError`.
"""

import sys
from dataclasses import dataclass, replace
from typing import Literal, assert_never

from esolangs.interpreters.io import IO

# Headings, as (d_row, d_col) with rows growing downward.
_UP = (-1, 0)
_DOWN = (1, 0)
_LEFT = (0, -1)
_RIGHT = (0, 1)
_HEADINGS = (_RIGHT, _DOWN, _LEFT, _UP)

# The spellings, as a type.  ``_parse`` is the only writer of ``self.nodes``
# and it copies out of :data:`_NODES`, so every spelling the interpreter ever
# dispatches on is one of these -- which lets ``_execute`` end in an ``else``
# that mypy narrows to the last one, rather than a branch nothing can take.
# Adding a node means adding it here as well as to ``_NODES``, or the tuple
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

# Node spellings, longest first: ``\[ ]/`` contains ``[ ]``, and ``[ }``,
# ``[ >`` and ``[ ]`` share a prefix, so a shorter spelling must never be
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

# Characters that carry a pointer between nodes.  Every one of these is a
# plain conduit: the headings it permits are derived from its shape.
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
    """Return the heading 90 degrees to the left of ``d``."""
    d_row, d_col = d
    return (-d_col, d_row)


def _turn_right(d: tuple[int, int]) -> tuple[int, int]:
    """Return the heading 90 degrees to the right of ``d``."""
    d_row, d_col = d
    return (d_col, -d_row)


@dataclass(frozen=True)
class _Pointer:
    """One program pointer: a position, a heading, a register, a cursor.

    ``row``/``col`` is the cell the pointer currently occupies, ``d`` the
    heading it is travelling on, ``reg`` its own register (``None`` when
    empty), and ``deque`` its index into the shared tape of deques.  A
    pointer that has reached an ``(( ))`` is ``done``.

    Frozen: a step returns the pointers that follow rather than editing the
    ones it was handed, so a pointer is a value.  ``replace`` builds the
    changed copy, and ``memory`` is a tuple of pairs so the whole pointer
    stays hashable -- which is what :meth:`state` already wanted it to be.
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
    memory: tuple[tuple[tuple[int, int], tuple[int, int]], ...] = ()

    def remembered(self, cell: tuple[int, int]) -> tuple[int, int] | None:
        """Return the heading this pointer last left ``cell`` on."""
        for key, value in self.memory:
            if key == cell:
                return value
        return None

    def remembering(self, cell: tuple[int, int], d: tuple[int, int]) -> "_Pointer":
        """Return this pointer with ``cell``'s exit heading recorded."""
        kept = tuple((k, v) for k, v in self.memory if k != cell)
        return replace(self, memory=(*kept, (cell, d)))

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
            tuple(sorted(self.memory)),
        )


class _Machine:
    """Per-run Flowchart state: the grid, its pointers, and the deques.

    ``step()`` advances every live pointer one cell, in creation order;
    ``halted`` is true once each has stopped on an ``(( ))``.  The machine
    is deterministic and its :meth:`snapshot` is bounded whenever the deques
    are, so ``esolangs.vm.run_until_halt_or_cycle`` can prove a hang on it;
    a program that grows a deque without bound falls into the same
    undetectable class as an ever-growing brainfuck tape.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Parse ``code``'s nodes and start on the first ``( )``."""
        self.io = io
        self.grid = [line.rstrip("\n") for line in code]
        self.width = max((len(r) for r in self.grid), default=0)
        self.grid = [r.ljust(self.width) for r in self.grid]

        # (row, col) -> (node spelling, col of the node's first character); every
        # cell a node covers maps to that node, so a pointer arriving at any
        # column of the box executes it.
        self.nodes: dict[tuple[int, int], tuple[_Spelling, int]] = {}
        self._parse()

        self.deques: dict[int, list[int]] = {}

        start = self._start()
        self.pointers = [_Pointer(start[0], start[1], _RIGHT)]
        self._fork_at_start()

    def _parse(self) -> None:
        """Record every node on the grid, longest spelling first."""
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
        """Reject a vertical path that enters a node off its middle.

        Runs after the scan above, because a rail's node may be recorded
        after the rail itself.  Only vertical arms are checked: a node is a
        contiguous run of cells on one row, so a horizontal neighbour can
        only ever be at ``col0 - 1`` or ``col0 + len``, and the cell it enters is
        therefore always an end cell.  Horizontal entry cannot be drawn any
        other way, which is why the spec constrains only the vertical case.
        """
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
        """Return the top-most, left-most ``( )`` node's first cell."""
        for row in range(len(self.grid)):
            for col in range(self.width):
                node = self.nodes.get((row, col))
                if node and node[0] == "( )" and node[1] == col:
                    return (row, col)
        raise ValueError("Flowchart program has no '( )' start node")

    def _fork_at_start(self) -> None:
        """Split the initial pointer if the start node has several exits.

        The start ``( )`` forks like any other, but there is no arriving
        heading to exclude, so every attached path gets a pointer.
        """
        p = self.pointers[0]
        here = (p.row, p.col)
        exits = self._reading_order(self._exits_from_node(p.row, p.col, None))
        if not exits:
            self.pointers[0] = replace(p, done=True)
            return
        self.pointers = [_Pointer(row, col, d, prev=here) for row, col, d in exits]

    def _cells_of(self, row: int, col: int) -> list[tuple[int, int]]:
        """Return every cell covered by the node at ``(row, col)``."""
        spelling, col0 = self.nodes[(row, col)]
        return [(row, col0 + i) for i in range(len(spelling))]

    @staticmethod
    def _reading_order(
        exits: list[tuple[int, int, tuple[int, int]]],
    ) -> list[tuple[int, int, tuple[int, int]]]:
        """Sort a fork's exits top-most first, then left-most.

        The spec orders pointers "top-most left-most, traveling right, then
        downwards", so a fork creates them in the reading order of the cells
        its paths leave through.  Only the fork sites sort: the unsorted
        enumeration also feeds :meth:`_leave`'s fallback, which the spec says
        nothing about.
        """
        return sorted(exits, key=lambda step: (step[0], step[1]))

    def _anchor(self, row: int, col: int) -> tuple[int, int]:
        """Return the key a cell's re-entry memory is stored under.

        A node is several cells wide and a rail may re-enter it at any of
        them, so every cell of a box shares its first cell's key; a bare
        path character is its own anchor.
        """
        node = self.nodes.get((row, col))
        return (row, node[1]) if node else (row, col)

    def _exits_from_node(
        self, row: int, col: int, came_from: tuple[int, int] | None
    ) -> list[tuple[int, int, tuple[int, int]]]:
        """Return the ``(row, col, heading)`` steps leaving the node at ``(row, col)``.

        A node's exits are the path cells and nodes touching any cell of its
        box, minus the cell the pointer entered from -- excluding by *cell*
        rather than by heading matters because a box is several cells wide,
        so a pointer can enter one cell of it from the north and still find
        that same northern cell offered again from a different column.
        ``came_from`` is ``None`` at the start, where nothing is excluded.

        Exits are counted per *destination*, not per cell of this box.  Two
        stacked nodes touch along their whole overlap, so a three-cell box
        sitting on another offers a step from each of its columns -- but all
        three land on the one node below, which is a single path onward, not
        three.  Counting them separately made a ``( )`` drawn directly above
        another node fork into three pointers that then walked the rest of
        the program in lock-step, tripling its output.  A rail between the
        two nodes never showed the bug, because only its middle column
        carries the ``│``; the wire's real job is narrowing a wide contact
        down to one path.  Deduplicating here means a drawing that omits it
        behaves the same way instead of silently multiplying pointers.
        """
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
                # A node is reached once however many of its cells touch this
                # box; a bare path cell is its own destination.
                node = self.nodes.get((n_row, n_col))
                target = (n_row, node[1]) if node else (n_row, n_col)
                if target in seen:
                    continue
                seen.add(target)
                out.append((n_row, n_col, d))
        return out

    def _in_bounds(self, row: int, col: int) -> bool:
        """Whether ``(row, col)`` is on the grid."""
        return 0 <= row < len(self.grid) and 0 <= col < self.width

    def _accepts(self, row: int, col: int, d: tuple[int, int]) -> bool:
        """Whether a pointer may enter ``(row, col)`` travelling on ``d``.

        A line character connects only in the directions its shape draws, so
        it can be entered exactly when one of those arms points back at the
        cell the pointer is coming from -- a ``┐`` reached travelling right
        is entered through its left arm and then turns down.
        """
        if not self._in_bounds(row, col):
            return False
        if (row, col) in self.nodes:
            return True
        c = self.grid[row][col]
        return c in _EXITS and (-d[0], -d[1]) in _EXITS[c]

    @property
    def halted(self) -> bool:
        """Whether every pointer has stopped."""
        return all(p.done for p in self.pointers)

    # The VM's language-shaped view.

    @property
    def ip(self) -> tuple[int, ...] | None:
        """The first pointer still running, or ``None`` once none is.

        A Flowchart program runs several pointers at once, so there is no
        single cursor to report: this is the first live one, as
        ``(row, col, drow, dcol)`` with the heading flattened, and ``None``
        once every pointer has stopped on an ``(( ))``.
        """
        for pointer in self.pointers:
            if not pointer.done:
                return (pointer.row, pointer.col, *pointer.d)
        return None

    @property
    def memory(self) -> list[int]:
        """The shared tape of deques, concatenated in index order.

        This is what the pointers read and write between them.
        """
        return [v for key in sorted(self.deques) for v in self.deques[key]]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(p.state() for p in self.pointers),
            tuple(sorted((k, tuple(v)) for k, v in self.deques.items() if v)),
            self.io.position(),
        )

    def step(self) -> None:
        """Advance every live pointer one cell, in creation order."""
        if self.halted:
            return
        for i in range(len(self.pointers)):
            if not self.pointers[i].done:
                self._advance(i)

    def _put(self, i: int, p: _Pointer) -> None:
        """Write ``p`` back as the ``i``th pointer.

        A pointer is frozen, so every change to one is a replacement.  The
        pointer *list* stays a list: a ``( )`` forks by appending, and the
        count grows with the program rather than with how long it runs.
        """
        self.pointers[i] = p

    def _advance(self, i: int) -> None:
        """Execute the cell under pointer ``i``, then move it one cell on."""
        p = self.pointers[i]
        if (p.row, p.col) in self.nodes:
            self._execute(i)
        else:
            self._follow_path(i)

    def _follow_path(self, i: int) -> None:
        """Move pointer ``i`` along the line character it is standing on."""
        p = self.pointers[i]
        c = self.grid[p.row][p.col]
        back = (-p.d[0], -p.d[1])
        allowed = [d for d in _EXITS.get(c, ()) if d != back]
        if not allowed:  # pragma: no cover - no line character has a single arm
            # A pointer only ever stands on a cell it entered legally, and
            # both _move and _exits_from_node gate on _accepts, so `back` is
            # always one of this cell's arms.  Removing it empties `allowed`
            # only for a one-armed character, and _EXITS has none -- but the
            # guard stays so adding one later stops rather than crashes.
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
        """Return ``p``'s remembered exit from ``(row, col)``, if it may be taken.

        The spec declines the remembered direction when following it would
        turn the pointer 180 degrees, so a rail that re-enters a cell head-on
        falls back to the ordinary rules instead.
        """
        d = p.remembered(self._anchor(row, col))
        if d is None or d not in allowed:
            return None
        if d == (-p.d[0], -p.d[1]):
            # The spec's 180-degree decline.  Unlike the other pragmas here
            # this is not a proof: a brute-force sweep of ~3M small grids
            # never reached it, but the rule comes from the wiki's worked
            # examples, so it stays.
            return None  # pragma: no cover - no known grid reaches it
        return d

    def _move(self, i: int, d: tuple[int, int]) -> None:
        """Step pointer ``i`` one cell along ``d``, stopping off the grid."""
        p = self.pointers[i]
        n_row, n_col = p.row + d[0], p.col + d[1]
        if not self._accepts(n_row, n_col, d):
            self._put(i, replace(p, done=True))
            return
        self._put(i, replace(p, prev=(p.row, p.col), row=n_row, col=n_col, d=d))

    def _leave(self, i: int, prefer: tuple[int, int] | None = None) -> None:
        """Move ``p`` off the node it occupies.

        ``prefer`` is a heading a node's own semantics have chosen (a
        switch's turn); when it is unavailable, or absent, the remembered
        direction settles the choice and the pointer's current heading
        breaks any remaining tie.
        """
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
        """Record the exit taken from the node and move to ``(row, col)``."""
        p = self.pointers[i]
        p = p.remembering(self._anchor(p.row, p.col), d)
        self._put(i, replace(p, prev=(p.row, p.col), row=row, col=col, d=d))

    def _fork(self, i: int) -> None:
        """Split pointer ``i`` across every path leaving a ``( )`` node.

        The pointer itself continues along the first exit and a new pointer,
        carrying a copy of the register and deque cursor, is appended for
        each of the others.
        """
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
        """Return ``p``'s currently selected deque, creating it if needed."""
        return self.deques.setdefault(p.deque, [])

    def _execute(self, i: int) -> None:
        """Run the node under pointer ``i``, then move it off that node.

        The register and deque cursor are computed into locals and written
        back once, since a pointer is a value: a node changes at most one
        of them, and the three nodes that route instead of computing
        (``(( ))``, ``( )``, ``< >``) return before the write-back.

        The deques stay a mutable dict on the machine.  They are shared by
        every pointer -- that sharing is the language's only channel
        between forks -- and a fork copies a pointer, not the tape.
        """
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
            # Unreachable, and checked to be: ``_Spelling`` is exhausted by
            # the arms above, so mypy narrows this to ``Never``.  A node added
            # to the type but not dispatched here fails the type check rather
            # than silently falling through to ``_leave``.
            assert_never(spelling)

        self._put(i, replace(p, reg=reg, deque=deque))
        self._leave(i)

    def _switch(self, i: int) -> None:
        """Route ``p`` by its register: 1 turns left, 0 right, empty goes on.

        Left and right are relative to the heading the pointer arrived on
        (see the module docstring); when the chosen side has no path
        attached, the spec sends the pointer straight forward instead.
        """
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
        """Read one bit of input, or ``None`` once the input is exhausted."""
        try:
            value = self.io.input_str()
        except (EOFError, IndexError):
            return None
        return 1 if value.strip() == "1" else 0


def run(code: list[str], io: IO) -> None:
    """Execute a Flowchart program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
