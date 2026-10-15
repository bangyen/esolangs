r"""Interpreter for Flowchart.

Nodes drawn as literal flowchart boxes are joined by box-drawing lines, and
one or more pointers walk those lines, executing the node they land on.
Each pointer owns a register holding a single bit (``0``, ``1``, or empty)
and a cursor into a shared, infinite tape of deques; the deques themselves
are shared by every pointer.  Execution starts on the left-most, top-most
``( )`` node travelling right, and the program halts once every pointer has
stopped on an ``(( ))``.

A vertical path enters a node at the node's middle.  The wiki says "vertical
paths connecting into a node are expected to connect to the middle of the
node", and all three worked examples (truth machine, cat, Kolakoski) obey it
-- 32 vertical attachments, every one centred.  Those same examples enter
nodes *horizontally* at their end cells 47 times (the Kolakoski program's top
row is one long horizontal chain), but the two are not in tension: a node is a
contiguous run of cells on one row, so a horizontal neighbour is always at
``col0 - 1`` or ``col0 + len`` and the cell it enters is always an end cell.
Horizontal entry cannot be drawn any other way, so the spec constrains only
the case a program can get wrong.  Vertical entry off the middle is
malformed.  This checks *entry*, not movement: a pointer already inside a
node still leaves through whichever cell of the box its exit sits on, and a
rail may still pass a node by without touching it.

Commands:
    The nodes, all of which the wiki (https://esolangs.org/wiki/Flowchart)
    tabulates explicitly.
    ``( )``: start / fork / no-op; the only node that splits.
    ``(( ))``: end; a pointer that reaches it stops.
    ``[ ]``: toggle the register (empty becomes 1).
    ``{ ]``: set the register to 0.
    ``[ }``: set the register to 1.
    ``{ }``: clear the register, making it empty.
    ``< >``: switch: 1 turns left, 0 turns right, empty goes on.
    ``/ /``: read one bit of input into the register.
    ``\ \``: output the register's bit (zero when it is empty).
    ``\[ ]/``: push the register onto the top of the deque.
    ``/[ ]\``: push the register onto the bottom of the deque.
    ``\{ }/``: pop the deque's top into the register.
    ``/{ }\``: pop the deque's bottom into the register.
    ``< ]``: select the previous deque.
    ``[ >``: select the next deque.

Input/output:
    I/O is byte-oriented, low bit first, as the spec says.  ``/ /`` takes the
    next bit of the current input byte and ``\ \`` buffers one bit of an
    output byte; a partial byte is zero-padded and written at halt.  Both
    wiki Hello Worlds then print ``Hello, world!`` itself, and the truth
    machine given ``0`` prints one zero bit, padded to a NUL byte.  Unicode
    input is reduced modulo 256.
    At EOF a ``/ /`` read leaves the register **empty** rather than raising
    (the spec's "empty if there are no more bits to read"), the state
    ``{ }`` clears it to; ``\ \`` then prints zero for it and a push puts it
    on the deque as an empty cell.  A program reading past EOF keeps running
    without a HaltError.  The wiki's cat pushes that empty and pops it last,
    so it echoes its input plus one zero bit, which pads to a trailing NUL.

Errors:
    ProgramError: Nodes touching side by side, an unknown node, a vertical
    path meeting a node off its middle, no ``( )`` to start from, a start
    node with no exit path, or a non-end node with no onward path.

Decisions:
    The spec leaves five things unstated that a running interpreter has to
    settle.  Each is resolved against the wiki's own worked examples, and all
    three (truth machine, cat, Kolakoski) are exercised by the test suite.
    * A switch's left and right are relative to the pointer's heading, not
      compass directions.  The truth machine's ``< >`` is entered travelling
      *downward*: register 1 has to reach the ``\ \`` that loops back (drawn
      grid-east) and register 0 the ``\ \`` and ``(( ))`` that halt (drawn
      grid-west).  Only heading-relative left/right puts 1 on the looping
      branch.
    * Re-entry memory disambiguates paths; it never suppresses a node.  The
      spec says a pointer re-entering a node or path it has already
      travelled "will go in the direction that it had previously travelled
      unless it were to turn it 180deg".  Read as a rule about *node
      semantics* it would break the wiki's cat program, whose ``< >`` nodes
      sit inside a loop and must decide differently on each lap, or the loop
      could never exit.  So a node's own semantics always run, and the
      remembered direction only settles genuine ambiguity: which way to
      leave a junction (a ``T``-shaped fork) or a node whose semantics do
      not name an exit.  The 180deg clause means the remembered direction is
      declined whenever taking it would reverse the pointer.
    * Empty is a value: it outputs zero and it is pushed like a bit.  The
      spec says "bits in a register and deque are also able to be an 'empty'
      value" and "outputting empty is the same as outputting zero", so a
      push of an empty register puts an empty on the deque and popping it
      empties the register again.  No wiki example forces the other reading
      (a push of empty being a no-op): the truth machine, cat and both Hello
      Worlds never touch a deque, and the Kolakoski program prints the
      Kolakoski sequence either way.  An earlier revision of the wiki's cat
      popped an exhausted deque before its last output and so appended a zero
      (``101`` in, ``1010`` out); the explicit output rule takes precedence.
    * A step runs one node per pointer; paths take no time.  The spec orders
      pointers "from the top-most left-most node, traveling right, then
      down, then finally oldest-to-newest", so each step every pointer rides
      its path to the next node and the pointers then execute in that order.
      The spec never says what a path cell costs, but the wiki's
      eight-pointer Hello World settles it: its rows start at different
      distances from the fork, and only node-counted time lines their output
      bits up.  The same program fixes the start as the *left-most*, then
      top-most, ``( )``, since a higher ``( )`` sits to its right.  A forking
      pointer keeps its forward-first exit (the spec's rule for any node but
      ``< >``); new pointers take the others in reading order, which the spec
      leaves open.  A pointer's deque cursor is unspecified; it is kept
      per-pointer, like the register.
"""

from bisect import bisect_left
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Literal, assert_never

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

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


class _Machine:
    r"""Per-run Flowchart shell: the grid, its pointers, and the deques.

    ``step()`` reads the input bits its ``/ /`` nodes need and writes the
    bytes its ``\\ \\`` nodes gather; the pure :func:`_advance` owns the
    pointers and deques and returns the next run plus the bytes to write.
    ``halted`` is true once each pointer has stopped on an ``(( ))``.  The
    run is deterministic and its :meth:`snapshot` is bounded whenever the
    deques are, so ``esolangs.vm.run_until_halt_or_cycle`` can prove a hang
    on it; a program that grows a deque without bound is as undetectable as
    an ever-growing brainfuck tape.
    """

    #: Whether a read past the end of the input yields a *value* here
    #: rather than raising.  A few languages do; the rest raise
    #: :class:`~esolangs.exceptions.InputExhaustedError`, which is the
    #: package norm and what :func:`esolangs.run` documents; this one does
    #: not, so an underfed program answers a different row of its table
    #: instead of refusing, and a caller has no way to tell from the output
    #: that it happened.
    #:
    #: Declared rather than changed.  The zero-beyond-input convention was
    #: audited against every wiki page and settled deliberately
    #: (``docs/limitations.md``, Interpreter conventions); rewriting it
    #: would be a decision about what these languages *mean*, not a fix.
    #: What was wrong was that nothing said so, so the promise ``run`` made
    #: was false for seven languages and a generic caller could not find
    #: out which.
    eof_is_a_value = True

    def __init__(self, code: list[str], io: IO) -> None:
        """Parse ``code``'s nodes and start on the first ``( )``."""
        self.io = io
        self._input_reads = 0
        # The input byte's unread bits and how many remain.  The machine
        # owns these because reading is the shell's job; the output byte a
        # partial write gathers is part of the pure run.
        self._incoming = self._remaining = 0
        rows = [line.rstrip("\n") for line in code]
        self.width = max((len(r) for r in rows), default=0)
        self.grid = tuple(r.ljust(self.width) for r in rows)

        # (row, col) -> (node spelling, col of the node's first character); every
        # cell a node covers maps to that node, so a pointer arriving at any
        # column of the box executes it.
        self.nodes: dict[tuple[int, int], tuple[_Spelling, int]] = {}
        self._parse()

        start = self._start()
        self.state = _Run(self._initial_pointers(start), MappingProxyType({}))

    @property
    def pointers(self) -> tuple[_Pointer, ...]:
        """The live pointers, as the transition last returned them."""
        return self.state.pointers

    @property
    def deques(self) -> Mapping[int, tuple[int | None, ...]]:
        """The shared deques, as the transition last returned them."""
        return self.state.deques

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
                        raise syntax_error(
                            f"unknown character {c!r} at ({col}, {row})",
                            (
                                "use Flowchart nodes and connected path glyphs; "
                                "keep other text outside the diagram"
                            ),
                        )
                    col += 1
        self._check_separation()
        self._check_alignment()

    def _check_separation(self) -> None:
        """Reject nodes touching side by side without a connecting path.

        Nodes may sit in adjacent rows: both wiki Hello Worlds stack their
        rows of ``{ ]``/``[ }`` boxes with no gap, and a box's exits are path
        cells, so a node above or below is simply not an exit.
        """
        for (row, col), node in self.nodes.items():
            neighbour = self.nodes.get((row, col + 1))
            if neighbour is not None and neighbour != node:
                raise syntax_error(
                    f"nodes touch without a path at ({col}, {row})",
                    "separate the nodes with a connecting path",
                )

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
                        raise syntax_error(
                            f"vertical path at ({col}, {row}) enters {spelling!r} at "
                            f"column {col}, but its middle is column {middle}",
                            "connect a vertical path at the middle column of the node",
                        )

    def _start(self) -> tuple[int, int]:
        """Return the left-most, then top-most, ``( )`` node's first cell.

        The spec starts on "the left-most top-most node" -- column first,
        unlike its top-most-first pointer order -- and the wiki's
        eight-pointer Hello World needs exactly that: its start sits at the
        left edge below a higher ``( )`` that only forks.
        """
        for col in range(self.width):
            for row in range(len(self.grid)):
                node = self.nodes.get((row, col))
                if node and node[0] == "( )" and node[1] == col:
                    return (row, col)
        raise syntax_error(
            "Flowchart program has no '( )' start node",
            "add a ( ) start node and connect its exit",
        )

    @property
    def halted(self) -> bool:
        """Whether every pointer has stopped."""
        return all(p.done for p in self.pointers)

    # The VM's language-shaped view.

    #: ``ip`` is a cell of the program's own rectangle: the first two
    #: parts are a row and a column, and the rest is a heading.  Without
    #: this a caller cannot tell the pair from a call depth or a frame
    #: stack, which look identical and mean somewhere else entirely.
    ip_shape = "grid"

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

        This is what the pointers read and write between them.  The view
        holds bits only, so an empty cell is left out of it; the snapshot
        keeps it.
        """
        return [
            v for key in sorted(self.deques) for v in self.deques[key] if v is not None
        ]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(p.state() for p in self.pointers),
            tuple(sorted((k, tuple(v)) for k, v in self.deques.items() if v)),
            self.io.progress(),
            self._input_reads,
            self._incoming,
            self._remaining,
            self.state.outgoing,
            self.state.used,
        )

    def step(self) -> None:
        r"""Run one node per live pointer, in the spec's pointer order.

        Hands the run, grid and bits to the pure :func:`_advance` and stores
        the result.  A command that still needs a bit raises
        :class:`_NeedBitError` carrying the bytes emitted so far; the shell
        flushes that prefix *before* it reads, retries, and flushes each
        later prefix once.  A fault carries the same prefix, flushed before
        it surfaces, so a byte an earlier pointer finished is written even
        when a later pointer fails.  Paths take no time: every pointer first
        rides its path to the next node, then the pointers execute ordered
        by that node -- top-most, then left-most, then oldest first.
        Pointers a fork creates join on the next step.
        """
        if self.halted:
            return
        bits: list[int | None] = []
        flushed: list[int] = []
        while True:
            try:
                run, printed = _advance(
                    self.state, self.grid, self.nodes, self.width, tuple(bits)
                )
            except _NeedBitError as request:
                # Flush what earlier pointers wrote before this read, so the
                # event order matches the pointer order that produced it.
                self._flush(request.printed, flushed)
                bits.append(self._read_bit())
                continue
            except BaseException as fault:
                # A later pointer's fault must not swallow a byte an earlier
                # one already finished.
                self._flush(getattr(fault, "printed", ()), flushed)
                raise
            self.state = run
            self._flush(printed, flushed)
            return

    def _flush(self, printed: tuple[int, ...], flushed: list[int]) -> None:
        """Write the bytes of ``printed`` beyond those already written."""
        delta = printed[len(flushed) :]
        for code in delta:
            self.io.print_char(chr(code))
        flushed.extend(delta)

    def _initial_pointers(self, start: tuple[int, int]) -> tuple[_Pointer, ...]:
        """Return the start node's initial pointers, one per attached path.

        The start ``( )`` forks like any other, but there is no arriving
        heading to exclude, so every attached path gets a pointer, the
        pointer's own first.
        """
        exits = _forward_first(
            _exits_from_node(self.grid, self.nodes, self.width, *start, None),
            _RIGHT,
        )
        if not exits:
            raise syntax_error(
                "start node has no exit path", "connect a path leaving the start node"
            )
        return tuple(_Pointer(row, col, d, prev=start) for row, col, d in exits)

    def _read_bit(self) -> int | None:
        """Read the next input bit, low bit first, or ``None`` at EOF."""
        if not self._remaining:
            try:
                self._incoming = self.io.input_char() % 256
            except (EOFError, IndexError):
                return None
            self._input_reads += 1
            self._remaining = 8
        bit = self._incoming & 1
        self._incoming >>= 1
        self._remaining -= 1
        return bit


class _NeedBitError(Exception):
    """Ask the shell for one more input bit a transition has run out of.

    Carries ``printed``: the output bytes the tick had already produced when
    it reached the read, so the shell can flush that prefix *before* it
    performs the read and keep the original event order.
    """

    def __init__(self, printed: tuple[int, ...]) -> None:
        super().__init__("the tick needs another input bit")
        self.printed = printed


def _in_bounds(grid: tuple[str, ...], width: int, row: int, col: int) -> bool:
    """Whether ``(row, col)`` is on the grid."""
    return 0 <= row < len(grid) and 0 <= col < width


def _cells_of(
    nodes: Mapping[tuple[int, int], tuple[_Spelling, int]], row: int, col: int
) -> list[tuple[int, int]]:
    """Return every cell covered by the node at ``(row, col)``."""
    spelling, col0 = nodes[(row, col)]
    return [(row, col0 + i) for i in range(len(spelling))]


def _accepts(
    grid: tuple[str, ...],
    nodes: Mapping[tuple[int, int], tuple[_Spelling, int]],
    width: int,
    row: int,
    col: int,
    d: tuple[int, int],
) -> bool:
    """Whether a pointer may enter ``(row, col)`` travelling on ``d``.

    A line character connects only in the directions its shape draws, so
    it can be entered exactly when one of those arms points back at the
    cell the pointer is coming from -- a ``┐`` reached travelling right
    is entered through its left arm and then turns down.
    """
    if not _in_bounds(grid, width, row, col):
        return False
    if (row, col) in nodes:
        return True
    c = grid[row][col]
    return c in _EXITS and (-d[0], -d[1]) in _EXITS[c]


def _anchor(
    nodes: Mapping[tuple[int, int], tuple[_Spelling, int]], row: int, col: int
) -> tuple[int, int]:
    """Return the key a cell's re-entry memory is stored under.

    A node is several cells wide and a rail may re-enter it at any of
    them, so every cell of a box shares its first cell's key; a bare
    path character is its own anchor.
    """
    node = nodes.get((row, col))
    return (row, node[1]) if node else (row, col)


def _reading_order(
    exits: list[tuple[int, int, tuple[int, int]]],
) -> list[tuple[int, int, tuple[int, int]]]:
    """Sort a fork's exits top-most first, then left-most."""
    return sorted(exits, key=lambda step: (step[0], step[1]))


def _forward_first(
    exits: list[tuple[int, int, tuple[int, int]]], d: tuple[int, int]
) -> list[tuple[int, int, tuple[int, int]]]:
    """Order a fork's exits: the pointer's own first, then reading order.

    "A pointer will always choose to go forward on a node if given
    multiple exit paths, followed by clockwise, then counterclockwise"
    names only ``< >`` as the exception, so the forking pointer keeps
    that exit and the new pointers take the rest in reading order.
    """
    exits = _reading_order(exits)
    order = (d, _turn_right(d), _turn_left(d), (-d[0], -d[1]))
    own = min(exits, key=lambda step: order.index(step[2]), default=None)
    return [] if own is None else [own, *(e for e in exits if e != own)]


def _exits_from_node(
    grid: tuple[str, ...],
    nodes: Mapping[tuple[int, int], tuple[_Spelling, int]],
    width: int,
    row: int,
    col: int,
    came_from: tuple[int, int] | None,
) -> list[tuple[int, int, tuple[int, int]]]:
    """Return the ``(row, col, heading)`` steps leaving the node at ``(row, col)``.

    A node's exits are the path cells touching any cell of its box, minus
    the cell the pointer entered from -- excluding by *cell* rather than
    by heading matters because a box is several cells wide, so a pointer
    can enter one cell of it from the north and still find that same
    northern cell offered again from a different column.  ``came_from`` is
    ``None`` at the start, where nothing is excluded.
    """
    out: list[tuple[int, int, tuple[int, int]]] = []
    for c_row, c_col in _cells_of(nodes, row, col):
        for d in _HEADINGS:
            n_row, n_col = c_row + d[0], c_col + d[1]
            # A neighbouring node is never an exit: the only nodes that may
            # touch are stacked in adjacent rows, with no path between.
            if (n_row, n_col) in nodes or not _in_bounds(grid, width, n_row, n_col):
                continue
            if (n_row, n_col) == came_from:
                continue
            if not _accepts(grid, nodes, width, n_row, n_col, d):
                continue
            out.append((n_row, n_col, d))
    return out


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


def run(code: list[str], io: IO) -> None:
    """Execute a Flowchart program."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run, shape="keep")
