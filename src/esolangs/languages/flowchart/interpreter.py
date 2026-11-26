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

from collections.abc import Mapping
from functools import partial
from types import MappingProxyType
from typing import Any

from esolangs.languages.flowchart._diagram import (
    _Image,
    _prepare_source,
)
from esolangs.languages.flowchart._transition import (
    _advance,
    _NeedBitError,
    _Pointer,
    _Run,
)
from esolangs.languages.flowchart.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._source import native_text_source
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime._validate import require_split_source
from esolangs.runtime.io import IO, _BufferedOutput

_WORKSPACE_MODEL = WorkspaceModel(
    "flowchart-v1",
    (
        "pointers",
        "deques",
        "input_cursor",
        "input_reads",
        "incoming",
        "remaining",
        "outgoing",
        "used",
    ),
)


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

    def __init__(self, code: list[str] | _Image, io: IO) -> None:
        """Parse ``code``'s nodes and start on the first ``( )``."""
        self.io = io
        self._writer = _BufferedOutput()
        self._input_reads = 0
        # The input byte's unread bits and how many remain.  The machine
        # owns these because reading is the shell's job; the output byte a
        # partial write gathers is part of the pure run.
        self._incoming = self._remaining = 0
        self._tick_input: list[int | None] = []
        self._tick_output = 0
        image = _prepare_source(code) if isinstance(code, list) else code
        self.grid, self.width, nodes, start, exits = image
        self.nodes = dict(nodes)
        pointers = tuple(_Pointer(row, col, d, prev=start) for row, col, d in exits)
        self.state = _Run(pointers, MappingProxyType({}))

    @property
    def pointers(self) -> tuple[_Pointer, ...]:
        """The live pointers, as the transition last returned them."""
        return self.state.pointers

    @property
    def deques(self) -> Mapping[int, tuple[int | None, ...]]:
        """The shared deques, as the transition last returned them."""
        return self.state.deques

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

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        pointers = tuple(
            (
                p.row,
                p.col,
                p.d,
                p.reg,
                p.deque,
                p.done,
                p.prev,
                frozenset(p.memory._exits.items()),  # noqa: SLF001 - owned logical map
            )
            for p in self.pointers
        )
        pending = self._pending_tick()
        return _WORKSPACE_MODEL.capture(
            pointers=(
                pointers
                if pending is None
                else WorkspaceVariant("pending_tick", (pointers, *pending))
            ),
            deques=frozenset((k, tuple(v)) for k, v in self.deques.items() if v),
            input_cursor=self.io.progress(),
            input_reads=self._input_reads,
            incoming=self._incoming,
            remaining=self._remaining,
            outgoing=self.state.outgoing,
            used=self.state.used,
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        state = (
            tuple(p.state() for p in self.pointers),
            tuple(sorted((k, tuple(v)) for k, v in self.deques.items() if v)),
            self.io.progress(),
            self._input_reads,
            self._incoming,
            self._remaining,
            self.state.outgoing,
            self.state.used,
        )
        pending = self._pending_tick()
        return state if pending is None else (*state, pending)

    def _pending_tick(self) -> tuple[tuple[int | None, ...], int] | None:
        """Retain effects that a retry must replay without repeating IO."""
        printed = self._tick_output + (self._writer.accepted or 0)
        if self._tick_input or printed:
            return tuple(self._tick_input), printed
        return None

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
        bits = self._tick_input
        while True:
            try:
                run, printed = _advance(
                    self.state, self.grid, self.nodes, self.width, tuple(bits)
                )
            except _NeedBitError as request:
                # Flush what earlier pointers wrote before this read, so the
                # event order matches the pointer order that produced it.
                self._flush(request.printed)
                bits.append(self._read_bit())
                continue
            except BaseException as fault:
                # A later pointer's fault must not swallow a byte an earlier
                # one already finished.
                self._flush(getattr(fault, "printed", ()))
                raise
            break
        self._flush(printed)
        self.state = run
        if bits or self._tick_output:
            bits.clear()
            self._tick_output = 0

    def _flush(self, printed: tuple[int, ...]) -> None:
        """Write beyond the accepted output prefix of this tick."""
        for code in printed[self._tick_output :]:
            char = chr(code)
            self._writer.write(self.io, char, first=partial(self.io.print_char, char))
            self._tick_output += 1

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


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the parsed grid and its startup paths."""
    source = require_split_source(source, options, "flowchart")
    image = _prepare_source(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: list[str] | _Image, io: IO) -> CompletionReport:
    """Execute a Flowchart program."""
    machine = _Machine(code, io)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: list[str], io: IO) -> None:
    """Execute a Flowchart program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run, shape="strip", loader=native_text_source)
