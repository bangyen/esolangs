"""Boolean-function generator for Minifuck (parameterized convention).

Minifuck's only input is ``.`` reading a byte when the eight-cell pool is
zero, which a boolean program cannot use without disturbing the pool it is
about to print.  So this follows the parameterized convention described in
:mod:`esolangs.tools.boolean.parameterized`: the template's ``{Xi}``
placeholders become ``[<`` (bit 1) or ``xx`` (bit 0) -- equal width, so no
instantiation leaks its inputs through its length -- and the harness builds
one program per input combination.

Four facts about the language carry the whole construction, each checked
against the interpreter rather than argued from the spec:

* ``[`` on a 1-cell clears it, XORs into ``ptr+1``, and skips one
  instruction; control flow rejoins after that single slot, so only *state*
  diverges, never the instruction stream.
* ``[x`` therefore advances the pointer exactly one cell whatever the crossed
  cell holds, which makes rightward walks position-deterministic over
  arbitrary junk.
* A ``[x``-walk leaves ``cell_i = NOT(old_i XOR w_{i-1})`` -- the complement
  of the running prefix-XOR of everything crossed.  The transform is affine
  and invertible, so re-crossing the stored bits loses nothing.
* ``<`` never writes and clamps at 0, so a long enough run of ``<``
  reconverges every path for free.

**How a program is built.**  Embed each input once, separated by one of
:data:`_SEPS`; walk to ``_BASE - 1``; emit a suffix (a run of ``[``, or for
one table a string with ``<`` interleaved); then run the endgame, which sets
the pool, relays a cell's value into the *pointer* -- values cannot travel
left in this language, but the pointer can -- and prints one ASCII digit.

The choice of ``(separator, settle count, suffix, accumulator)`` is what
makes a table build, and :data:`_PLANS` records one per truth table.  The
selection rule is the load-bearing part: pick the accumulator whose column
reads correctly **at the read**, not the cell that holds the answer
beforehand.  Those differ, because the walk out applies the running
prefix-XOR -- an AND column can arrive as a constant, and XOR can arrive as a
projection.  Choosing pre-walk covers 10 of the 16 two-input tables and looks
nearly right, which is the trap.

A table and its complement share a staging, so the plans are keyed by the
lexicographically smaller of the two: the endgame tries both read polarities
and prints ``NOT(v XOR cell7)``, so the complement costs nothing.

**Coverage.**  Every table at ``n <= 3`` builds from a staging, with no
search: 16 of 16 at two inputs, 256 of 256 at three, the whole three-input
arity in about ten seconds.  Wider tables fall through to the searches below,
which is why those remain -- a missing staging degrades rather than raises.
A table that ignores some inputs is solved at the arity it uses and renumbered
back, so a wide table with a narrow core is as cheap as that core.

Nothing here is hand-tracked: :class:`_Joint` runs all ``2**n`` instantiations
in lockstep as the template is emitted, every choice is made against the
simulated truth, and :func:`minifuck` raises rather than returning a program
it has not seen print the table.

``docs/walls.md`` carries the history this docstring used to: which
mechanisms were disproved outright, which were merely unfound, what the
runtime-read model reaches, and how the staged route came to cover tables the
searches fail on.
"""

import re
from collections import deque
from collections.abc import Callable
from functools import cache

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["minifuck"]

# What an acceptance callback keeps: each search names its own result type,
# and returning None means "keep looking".

# Where the embedded bits start.  The pool is cells 0..7, so the working area
# begins past it with a little room for the walk-in.
_BASE = 16

# What separates one embedded bit from the next.  A plain ``[x`` run leaves
# the prefix-XORs too correlated for the one-sided tests the endgame makes;
# the ``<`` steps back over a cell so the parities stay distinguishable.
#
# The separator decides the affine picture the whole construction reads from,
# and the first two here were picked by hand.  That turned out to be the
# binding constraint rather than a detail: between them they leave only 92
# distinct columns standing, and 112 of the 120 tables the searches could not
# reach were absent from the tape entirely rather than merely hard to print.
# Enumerating short strings over the same alphabet fixed that -- the three
# added below carry 118 of those 120, and the searches never had to change.
# Only the first two are used by the routes that scan separators (the
# degenerate path and the fallback searches); the rest are reached by name
# from :data:`_THREE_INPUT_PLAN`, so adding one costs those routes nothing.
_SEPS = ("[x<[x", "[x[x[x", "[<[<[", "[[[[[", "[x[<[")
_SEP = _SEPS[0]

# The separators the scanning routes try.  Widening this would multiply every
# search's cost; the plan reaches the others directly instead.
_SCAN_SEPS = _SEPS[:2]

# How far the bits and their working area reach, for sizing the windows.
_SPAN = 6

# The pool spells ASCII '0' (0b00110000) or '1' (0b00110001), so cells 0..6
# are fixed and cell 7 carries the answer.
_POOL = (0, 0, 1, 1, 0, 0, 0)

# The two reads.  ``[<`` leaves the pointer at ``(acc-1) + v``; ``[x<[<``
# leaves it at ``(acc-1) + NOT v``, restores the cell, and flips its
# neighbour unconditionally.  The printed digit is ``NOT(v XOR cell7)`` and
# every reachable pool conserves that XOR, so the read polarity -- not the
# pool -- is what makes a table and its complement both printable.
_READS = ("[<", "[x<[<")

# Depth caps for the two searches.  Both are joint searches over 2**n
# machines, so the cost is exponential in the cap; these are the smallest
# values that cover every two-input table.
_COLUMN_DEPTH = 13
_POOL_DEPTH = 16

# The parked search is the fallback, and the deepest of the three; it needs
# 15 to cover the XOR family.  ``_PARKED_LIMIT`` candidates are collected
# because which one survives the endgame is settled by running it.
_PARKED_DEPTH = 15
_PARKED_LIMIT = 12

# Re-crossings of the bit region before the parked search.  Each advances the
# affine state, which offers the search a different set of columns.
_SETTLE = 2


class _Sim:
    """A Minifuck machine fed one instruction at a time.

    The shipped interpreter takes its whole program up front, which an
    emitter cannot do -- it must advance a machine and branch on the result.
    This mirrors ``_Machine.step`` exactly while accepting instructions
    singly.  ``dead`` marks the one transition a parameterized program must
    never take: a ``.`` on a zero pool reads a byte of input.
    """

    __slots__ = ("dead", "out", "ptr", "skip", "tape")

    def __init__(self, size: int) -> None:
        """Start with a zeroed tape of ``size`` cells at the origin."""
        self.tape = [0] * size
        self.ptr = 0
        self.out: list[str] = []
        self.dead = False
        self.skip = False

    def copy(self) -> "_Sim":
        """Return an independent copy, for branching a search or a probe."""
        clone = _Sim.__new__(_Sim)
        clone.tape = list(self.tape)
        clone.ptr = self.ptr
        clone.out = list(self.out)
        clone.dead = self.dead
        clone.skip = self.skip
        return clone

    def key(self) -> tuple[object, ...]:
        """Return the whole state, hashable, so a search can dedup on it."""
        return (tuple(self.tape), self.ptr, tuple(self.out), self.dead, self.skip)

    def exec(self, ins: str) -> None:
        """Execute one instruction, mirroring ``_Machine.step``."""
        if self.dead:
            return
        if self.skip:
            self.skip = False
            return
        if ins == "<":
            if self.ptr:
                self.ptr -= 1
        elif ins in ".[":
            self.ptr += 1
            if self.ptr + 1 >= len(self.tape):
                self.tape.append(0)
            self.tape[self.ptr] ^= 1
            if ins == ".":
                value = int("".join(map(str, self.tape[:8])), 2)
                if value:
                    self.out.append(chr(value))
                else:
                    self.dead = True
            elif not self.tape[self.ptr]:
                self.tape[self.ptr + 1] ^= 1
                self.skip = True


def _set_bit(bit: int) -> str:
    """Return the ``{Xi}`` fill writing ``bit`` at ``ptr+1``.

    Both spellings are two characters and leave the pointer where they found
    it, so every instantiation has the same length -- without that, the
    program's length would leak the inputs it is meant to be evaluating.
    """
    return "[<" if bit else "xx"


class _Joint:
    """The ``2**n`` instantiations, advanced in lockstep as code is emitted."""

    def __init__(self, n: int, size: int = 512) -> None:
        """Start one machine per row of the truth table."""
        self.n = n
        self.rows = [[(r >> (n - 1 - k)) & 1 for k in range(n)] for r in range(2**n)]
        self.ms = [_Sim(size) for _ in self.rows]
        self.parts: list[str] = []

    def emit(self, code: str) -> None:
        """Append code and run it on every row, keeping them in lockstep."""
        self.parts.append(code)
        for m in self.ms:
            for ch in code:
                m.exec(ch)

    def emit_setter(self, i: int) -> None:
        """Emit the ``{Xi}`` placeholder, simulating each row with its bit."""
        self.parts.append("{X" + str(i) + "}")
        for bits, m in zip(self.rows, self.ms, strict=True):
            for ch in _set_bit(bits[i]):
                m.exec(ch)

    def fork(self) -> "_Joint":
        """Return a copy, for trying a continuation without committing."""
        clone = _Joint.__new__(_Joint)
        clone.n = self.n
        clone.rows = self.rows
        clone.ms = [m.copy() for m in self.ms]
        clone.parts = list(self.parts)
        return clone

    def col(self, cell: int) -> tuple[int, ...]:
        """Return ``cell``'s value across the rows -- the function it holds."""
        return tuple(m.tape[cell] for m in self.ms)

    def ptrs(self) -> tuple[int, ...]:
        """Return each row's pointer, so callers can see divergence."""
        return tuple(m.ptr for m in self.ms)

    def printed(self) -> list[str]:
        """Return what each row has printed so far."""
        return ["".join(m.out) for m in self.ms]

    def template(self) -> str:
        """Return the emitted template, ``{Xi}`` placeholders included."""
        return "".join(self.parts)


def _walk_to(j: _Joint, target: int) -> None:
    """Walk right to ``target`` with ``[x``, which is safe over any junk."""
    ptrs = set(j.ptrs())
    if len(ptrs) != 1:
        raise ValueError(f"walk needs a converged pointer, got {ptrs}")
    cur = ptrs.pop()
    if target < cur:
        raise ValueError(f"cannot walk left with [x ({cur} -> {target})")
    j.emit("[x" * (target - cur))


def _clamp(j: _Joint) -> None:
    """Clamp every row's pointer to 0.  ``<`` never writes, so this is free."""
    j.emit("<" * (max(j.ptrs()) + 1))


def _embed(n: int, settle: int = 0, sep: str = _SEP) -> _Joint:
    """Emit the embed: each ``{Xi}`` once, separated by :data:`_SEP`.

    The separator is not arbitrary.  A plain run of ``[x`` leaves the bits'
    prefix-XORs too correlated for the one-sided tests the endgame can make,
    and the XOR family becomes unreachable; ``[x<[x`` steps back over one
    cell so the parities stay distinguishable.  ``settle`` re-crosses the
    region that many times, which advances the affine state and offers the
    searches a different set of columns.
    """
    j = _Joint(n)
    _walk_to(j, _BASE - 1)
    for i in range(n):
        j.emit_setter(i)
        j.emit("[x")
        if i + 1 < n:
            j.emit(sep)
    for _ in range(settle):
        _clamp(j)
        _walk_to(j, _BASE - 1)
    return j


def _search[Hit](
    j: _Joint,
    accept: Callable[[list[_Sim], str], Hit | None],
    maxlen: int,
) -> Hit | None:
    """Breadth-first over ``<[x`` from the live joint state.

    ``accept`` sees the advanced machines and returns a result (or None).
    Searching from the *live* state is what makes the junk already on the
    tape part of the starting condition rather than a precondition to
    establish -- and the search must start with the pointer in the data, not
    at the origin: a depth-``d`` walk from cell 0 never reaches cell
    ``_BASE``, so every state it can see is input-independent.
    """
    root = tuple(m.copy() for m in j.ms)
    seen = {tuple(m.key() for m in root)}
    queue = deque([(root, "")])
    while queue:
        states, prog = queue.popleft()
        if len(prog) >= maxlen:
            continue
        for ch in "<[x":
            new = []
            for m in states:
                clone = m.copy()
                clone.exec(ch)
                new.append(clone)
            # A dead row can no longer be steered, so a state holding one is
            # not worth expanding.  Nothing in the alphabet below kills a row
            # -- only a print does -- so this fires on a state that arrived
            # dead, not on one this search killed.
            if any(m.dead for m in new):
                continue
            key = tuple(m.key() for m in new)
            if key in seen:
                continue
            seen.add(key)
            code = prog + ch
            if not any(m.skip for m in new):
                hit = accept(new, code)
                if hit is not None:
                    return hit
            queue.append((tuple(new), code))
    return None


def _find_pool(
    j: _Joint, cell7: int, walk_out: int, maxlen: int = _POOL_DEPTH
) -> str | None:
    """Find code leaving the pool correct once walked out to ``walk_out``.

    The pool must read ``0011000`` plus ``cell7`` at print time, and the walk
    out to the accumulator crosses it -- so what matters is the pool *after*
    that walk, not at the moment the code ends.

    Memoised, because this is where the module's time goes: one call is a
    breadth-first search costing 17-26ms at ``n == 3``, :func:`_try_print`
    makes four of them per accumulator, and every caller sweeps accumulators.
    The answer does not depend on the truth table -- only on the machines'
    own state -- so the same handful of searches was being repeated for every
    table.  Keying on the whole joint state would be sound but would rarely
    hit; keying on what this function actually reads is what makes it useful.
    A staging enumeration at ``n == 3`` fell from 173s to 0.5s on 6 distinct
    keys against 4530 lookups, returning the identical column set.
    """
    key = (
        tuple(tuple(m.tape) for m in j.ms),
        tuple(m.ptr for m in j.ms),
        tuple(m.skip for m in j.ms),
        tuple(m.dead for m in j.ms),
        cell7,
        walk_out,
        maxlen,
    )
    if key in _POOL_CACHE:
        return _POOL_CACHE[key]
    found = _find_pool_uncached(j, cell7, walk_out, maxlen)
    _POOL_CACHE[key] = found
    return found


# Keyed on everything :func:`_find_pool` reads, so a hit cannot be a
# different question wearing the same key.  It stays small in practice -- a
# dozen entries across both arities -- because the pool is driven to the same
# few states whatever the staging.
_POOL_CACHE: dict[tuple[object, ...], str | None] = {}


def _find_pool_uncached(
    j: _Joint, cell7: int, walk_out: int, maxlen: int = _POOL_DEPTH
) -> str | None:
    """The search :func:`_find_pool` memoises.  See it for what and why."""
    target = (*_POOL, cell7)

    def accept(new: list[_Sim], code: str) -> str | None:
        if len({m.ptr for m in new}) != 1:
            return None
        probe = [m.copy() for m in new]
        steps = walk_out - probe[0].ptr
        if steps < 0:
            return None
        for _ in range(steps):
            for ch in "[x":
                for m in probe:
                    m.exec(ch)
        for cell in range(8):
            col = {m.tape[cell] for m in probe}
            if len(col) != 1 or probe[0].tape[cell] != target[cell]:
                return None
        return code

    return _search(j, accept, maxlen)


def _endgame(j: _Joint, acc: int, read: str, cell7: int) -> None:
    """Set the pool, relay ``acc`` into the pointer, and print one digit.

    The walk back to the pool is measured from the read's *entry*: a
    constant-1 column diverges every row alike, so the pointer's minimum sits
    one cell further right than for a column with a zero row, and measuring
    from there would short the walk by one.
    """
    if acc < 8:
        raise ValueError("accumulator must sit past the pool")
    code = _find_pool(j, cell7, acc - 1)
    if code is None:
        raise ValueError("no pool pattern for this orientation")
    j.emit(code)
    _walk_to(j, acc - 1)
    j.emit(read)
    j.emit("<" * (acc - 7))
    # ``_find_pool`` accepts a code only after checking the pool *past* the
    # walk out, which is the state reached here -- so this is that check
    # restated on what was actually emitted rather than on a simulated walk.
    # It is an AssertionError rather than a ValueError deliberately: the two
    # disagreeing is a bug in the pair, and ``_try_print`` swallows every
    # ValueError, which would turn it into a silently skipped accumulator.
    for cell in range(8):
        if len(set(j.col(cell))) != 1:
            raise AssertionError(f"pool cell {cell} is input-dependent")
    j.emit("[x.")


def _try_print(j: _Joint, truth_table: str, acc: int) -> _Joint | None:
    """Try every read and orientation at ``acc``; return one that prints."""
    for read in _READS:
        for cell7 in (0, 1):
            probe = j.fork()
            try:
                _endgame(probe, acc, read, cell7)
            except ValueError:
                continue
            if probe.printed() == list(truth_table):
                return probe
    return None


def _find_column(
    j: _Joint, target: tuple[int, ...], window: int, maxlen: int
) -> tuple[str, int] | None:
    """Find code after which some cell holds ``target`` (or its complement)."""
    comp = tuple(1 - v for v in target)

    def accept(new: list[_Sim], code: str) -> tuple[str, int] | None:
        for cell in range(1, window):
            col = tuple(m.tape[cell] for m in new)
            if col in (target, comp):
                return code, cell
        return None

    return _search(j, accept, maxlen)


def _find_parked(
    j: _Joint, target: tuple[int, ...], window: int, maxlen: int, limit: int
) -> list[tuple[str, int]]:
    """Find states holding ``target`` with the pointer parked to read it.

    Producing the column is not enough on its own: walking back to it
    re-crosses, and so changes, the very cell.  Requiring the pointer to sit
    immediately left of the answer removes that walk, and several candidates
    are collected because which one survives the endgame is decided by
    running it, not by predicting it.
    """
    comp = tuple(1 - v for v in target)
    hits: list[tuple[str, int]] = []

    def accept(new: list[_Sim], code: str) -> list[tuple[str, int]] | None:
        ptrs = {m.ptr for m in new}
        if len(ptrs) != 1:
            return None
        cell = ptrs.pop() + 1
        if not 8 <= cell < window:
            return None
        col = tuple(m.tape[cell] for m in new)
        if col in (target, comp):
            hits.append((code, cell))
            if len(hits) >= limit:
                return hits
        return None

    return _search(j, accept, maxlen) or hits


# Where the embed leaves the first two inputs and the constants, whatever the
# arity: the carry chain preserves ``b0`` and ``b1`` individually before the
# prefix-XOR starts mixing, so these cells are fixed rather than searched.
# Later inputs are *not* here at any settle count -- the affine transform
# fixes which bits stay separable -- but a column search finds them in a
# fraction of a second, which is why the degenerate path still beats the
# ladder without being wholly search-free.
_DEGENERATE_CELLS = {
    "const1": 1,
    "~b0": 16,
    "b0": 17,
    "const0": 18,
    "~b1": 19,
    "b1": 20,
}


def _essential_inputs(truth_table: str, n: int) -> list[int]:
    """Which inputs the table actually depends on."""
    return [
        i
        for i in range(n)
        if any(
            truth_table[row] != truth_table[row ^ (1 << (n - 1 - i))]
            for row in range(2**n)
        )
    ]


def _degenerate(
    truth_table: str, n: int, *, fixed_cells_only: bool = False
) -> str | None:
    """Build a table depending on at most one input, without the ladder.

    Such a table is a constant, a projection, or a negated projection, and
    every one of those already stands as a *column* somewhere after the
    embed -- at a known cell for the first two inputs, and at a cheaply
    searched one beyond that.  So the whole construction is: find the cell
    holding the answer, then run the endgame on it.

    This is the piece that composes upward: a table with ``k`` essential
    inputs is a ``k``-input problem whatever its arity, so four of the
    fourteen three-input orbits are handled here for free.

    ``fixed_cells_only`` stops after the six known cells, skipping the column
    search.  That is for the caller who has a working fallback and wants a
    cheap *attempt* rather than an answer: the search costs about five
    seconds to fail at ``n == 3`` and the lookup under one, and every table
    the name-order caller below wins is won at the lookup.
    """
    want = tuple(int(c) for c in truth_table)
    base = _embed(n, sep=_SEP)
    _clamp(base)

    # The fixed cells first, then a search for the rest.
    candidates = list(_DEGENERATE_CELLS.values())
    for acc in candidates:
        hit = _try_print(base, truth_table, acc)
        if hit is not None:
            return hit.template()

    if fixed_cells_only:
        return None

    probe = _embed(n, sep=_SEP)
    _clamp(probe)
    _walk_to(probe, _BASE - 1)
    found = _find_column(probe, want, _BASE + n * _SPAN + 14, _COLUMN_DEPTH)
    if found is None:
        return None
    probe.emit(found[0])
    _clamp(probe)
    for acc in range(9, _BASE + n * _SPAN + 14):
        hit = _try_print(probe, truth_table, acc)
        if hit is not None:
            return hit.template()
    return None


def _project(truth_table: str, essential: list[int], n: int) -> str:
    """Rewrite the table over its essential inputs only.

    A table that ignores some of its inputs is a smaller table wearing extra
    ones.  Reading it at the essential positions gives that smaller table,
    which is a ``len(essential)``-input problem however wide the original was.
    """
    k = len(essential)
    rows = []
    for row in range(2**k):
        full = 0
        for slot, i in enumerate(essential):
            if (row >> (k - 1 - slot)) & 1:
                full |= 1 << (n - 1 - i)
        rows.append(truth_table[full])
    return "".join(rows)


# How far to search for a reconverging reset, and how many to try.  The
# first one is found at length 12 and is the one that builds, but the cap is
# a little higher so the search is not pinned to that exact string.
_RESET_DEPTH = 13
_RESET_LIMIT = 4


def _find_reset(ignored: int, maxlen: int = _RESET_DEPTH) -> list[str]:
    """Find code after which the ignored inputs leave no trace.

    The setters for the inputs a table ignores still have to be emitted --
    the harness has a bit for every input -- and emitting them first is what
    keeps the placeholders in name order.  They do write the tape, though,
    so what follows must erase the difference: this searches for a suffix
    after which all ``2**ignored`` rows are in *identical* states.

    Identical, not blank.  A blank tape is unreachable -- the all-ones row
    ends a cell to the right of the others and ``<`` clamps without writing,
    so the rows cannot be driven back to the origin together -- but they can
    be driven to a common non-blank state, which is all the rest of the
    construction needs.
    """
    j = _Joint(ignored)
    for i in range(ignored):
        j.emit_setter(i)
    hits: list[str] = []

    def accept(new: list[_Sim], code: str) -> list[str] | None:
        if len({m.key() for m in new}) != 1:
            return None
        hits.append(code)
        return hits if len(hits) >= _RESET_LIMIT else None

    _search(j, accept, maxlen)
    return hits


def _reconverged(truth_table: str, essential: list[int], n: int) -> str | None:
    """Build by emitting the ignored inputs first, then erasing them.

    ``_lift`` puts the ignored placeholders last, which leaves name order.
    The alternative is to emit them *first* -- ``{X0}``..``{Xn-1}`` stays
    ascending -- and then reconverge the rows so nothing downstream can tell
    which bits they were.  After that the table is a one-input problem in its
    single essential input, and the rest is the embed geometry every other
    degenerate table uses.

    The walk to ``_BASE - 1`` before the essential setter is what makes this
    cheap rather than a fresh search: it reproduces the standard embed, so
    the essential input lands on the cells :data:`_DEGENERATE_CELLS` already
    names and the fixed-cell lookup decides in a fraction of a second.  The
    junk the reset leaves behind is not a problem -- the rows are identical
    by then, so it is a constant starting condition, which is exactly what
    the searches here are built to run from.
    """
    if not 1 <= len(essential) <= 2:
        return None
    ignored = [i for i in range(n) if i not in essential]
    if ignored != list(range(len(ignored))):
        # The ignored inputs have to be the *leading* ones for emitting them
        # first to keep the order ascending.
        return None

    # Where to look for the answer once the ignored inputs are gone.  One
    # essential input leaves a projection, which stands at a known cell; two
    # leave a two-input table, which has a staging of its own -- so replay
    # that staging and read its own accumulator rather than scanning.  The
    # scan is what costs: at two essential inputs it turns a 0.5s build into
    # seconds without reaching anything the staging does not.
    if len(essential) == 1:
        setup: tuple[int, int, int] | None = None
        accumulators: tuple[int, ...] = tuple(_DEGENERATE_CELLS.values())
    else:
        inner = _project(truth_table, essential, n)
        complement = "".join(str(1 - int(c)) for c in inner)
        plan = _TWO_INPUT_PLAN.get(min(inner, complement))
        if plan is None:
            return None
        sep_index, _settle, brackets, acc = plan
        # Every two-input staging is a plain bracket run; the literal-suffix
        # form is only used by one three-input entry, and replaying it here
        # would need the walk this route does not make.
        if not isinstance(brackets, int):
            return None
        setup = (sep_index, brackets, acc)
        accumulators = (acc,)

    for reset in _find_reset(len(ignored)):
        j = _Joint(n)
        for i in ignored:
            j.emit_setter(i)
        j.emit(reset)
        if len({m.key() for m in j.ms}) != 1:
            continue
        _walk_to(j, _BASE - 1)
        if setup is None:
            j.emit_setter(essential[0])
            j.emit("[x")
        else:
            sep_index, brackets, _acc = setup
            for slot, i in enumerate(essential):
                j.emit_setter(i)
                j.emit("[x")
                if slot + 1 < len(essential):
                    j.emit(_SEPS[sep_index])
            _clamp(j)
            _walk_to(j, _BASE - 1)
            j.emit("[" * brackets + "<")
        _clamp(j)
        for acc in accumulators:
            hit = _try_print(j, truth_table, acc)
            if hit is not None:
                return hit.template()
    return None


# The two-input construction: one staging per complement pair.
#
# The embed leaves an affine picture -- every cell holds ``a*b0 ^ b*b1 ^ c``
# plus the one nonlinear term the ``[`` cascade computes -- and a plain run
# of ``k`` brackets from ``_BASE - 1`` sweeps that picture forward, exposing
# a different function at each step.  So the whole two-input problem is:
# pick the separator, the bracket count and the accumulator, then hand the
# result to the endgame every other route already uses.
#
# Selection is on the accumulator's value **at the read**, not on the cell
# that holds the answer beforehand.  Those differ, because the walk out
# applies the running prefix-XOR: at ``acc = 22`` after separator 1, AND
# ``(0,0,0,1)`` arrives as the constant ``(1,1,1,1)``, and XOR ``(0,1,1,0)``
# arrives as ``b1``.  Choosing on the pre-walk column is what made an
# earlier version of this table cover 10 of 16 rather than all of them.
#
# There are eight stagings for sixteen tables because a table and its
# complement always share one: the endgame tries both read polarities and
# both pool orientations, and the printed digit is ``NOT(v XOR cell7)``, so
# the complement costs nothing to reach.  Each entry was derived by running
# the staging forward and reading off the arriving column -- no program
# search -- and every one is checked end to end by the test suite.
# Each entry is ``(separator index, settle count, bracket count, accumulator)``
# keyed by the lexicographically smaller of a table and its complement.
# The third field is a bracket *count* for all but one entry, and a literal
# suffix string for that one.  See :func:`_staged`.
_Staging = tuple[int, int, int | str, int]

_TWO_INPUT_PLAN: dict[str, _Staging] = {
    "0000": (0, 0, 0, 9),  # constants
    "0011": (0, 0, 0, 16),  # b0
    "0101": (0, 0, 0, 19),  # b1
    "0110": (0, 0, 1, 19),  # XOR
    "0111": (0, 0, 4, 20),  # OR
    "0001": (1, 0, 0, 21),  # AND
    "0010": (0, 0, 5, 20),  # b0 AND NOT b1
    "0100": (0, 0, 6, 20),  # NOT b0 AND b1
}

# The same construction at three inputs.  It very nearly covers the arity --
# 108 of the 109 complement pairs are here -- but a miss still falls through
# to the searches rather than raising, so coverage cannot regress and the one
# last pair (``01101101`` / ``10010010``) needed a staging the others do not.
#
# It is worth knowing why, because it was the hardest table here by some
# margin and the searches never built it at all -- both members raise after
# about 96 seconds.  Its answer column is not scarce: 14375 of 804600 sparse
# suffixes leave it standing somewhere on the tape.  What is scarce is a
# staging that also *carries* it to the read, because the walk's prefix-XOR
# rewrites the very cell.  A pure bracket run never manages it; the suffix
# below interleaves two ``<`` into the run, which is the vocabulary the
# column search was already using when it found the column and still failed
# to print it.
#
# That pair was looked for and not found, and the shape of the miss is worth
# recording so it is not re-run blind.  Unlike the tables the new separators
# closed, its answer *is* computed: ``01101101`` stands as a column at cell 24
# under separator 2 at ``k == 15``.  What fails is the carry -- no accumulator
# reads it intact, and from that staging it arrives as ``10011101`` or
# ``01100010``, neither the table nor its complement.  A sweep over 13 of the
# 15 (separator, settle) slices at ``k <= 40`` and every accumulator found no
# staging that delivers it; the two skipped slices scored worst on a cheap
# distance screen, and the five that scored best -- reaching Hamming distance
# 1 but never 0 -- were all covered and all missed.
#
# It is a gap in this family, not a wall: 180 of the 256 possible columns
# arrive across the family, and no affine invariant separates them from this
# one (all 255 parity masks checked), so nothing here forbids it.
#
# What closed the gap was not a better search but a wider *separator* set.
# See the note on :data:`_SEPS`: the first two separators leave only 92
# distinct columns standing, and 112 of the 120 tables the searches could not
# reach did not stand as a column at all.  Three more separators carry 118 of
# those 120, every one of which builds, computes and emits in name order.
#
# The bracket axis is *exhausted*, not capped, and that is checkable rather
# than assumed.  Nothing in this language writes leftward -- ``[`` writes at
# ``ptr + 1`` and, on the cascade, ``ptr + 2``, and the pointer only ever
# advances -- so once every row's pointer has passed the accumulator window,
# no further bracket can change a staged column.  Measured, the columns stop
# changing between ``k == 25`` and ``k == 38`` depending on separator and
# settle count, so the sweep ran to 40 and anything past it is provably
# redundant.  Stopping at 30 would have been a cap rather than a bound, and
# would have missed real tables: nine of the entries below need 14 to 22.
#
# The other two axes were *sampled* rather than exhausted and came back
# empty -- settle counts 3 to 5 and accumulators 36 to 47 reached nothing the
# shipped stagings did not.  That is evidence they are barren, not proof.
#
# **This table is close to its natural size, which was measured rather than
# assumed.**  The 109 entries use 63 distinct ``(separator, settle, suffix)``
# stagings; a greedy minimum cover needs 35, and it still needs *all five*
# separators and both settle counts, with twelve stagings carrying a single
# pair each.  So there is no smaller vocabulary hiding here, and rewriting
# 108 verified entries to consolidate stagings would churn working constants
# for a count no caller sees.  Declined deliberately.
#
# Two related things also look removable and are not.  ``_SETTLE`` is unused
# by both plans but parameterises the parked search, which still serves
# ``n >= 4``; and the searches themselves are unreachable at ``n <= 3`` yet
# are what a wider table falls through to.  Neither is dead.
_THREE_INPUT_PLAN: dict[str, _Staging] = {
    "00000001": (0, 0, 10, 23),
    "00000110": (1, 1, 11, 27),
    "00001000": (0, 1, 8, 23),
    "00001110": (1, 0, 1, 26),
    "00010010": (0, 1, 6, 22),
    "00010100": (0, 0, 9, 23),
    "00010101": (0, 0, 9, 22),
    "00010111": (1, 0, 0, 25),
    "00011000": (1, 0, 1, 25),
    "00011001": (0, 1, 8, 22),
    "00011110": (0, 0, 1, 22),
    "00100001": (0, 1, 7, 22),
    "00100110": (1, 1, 12, 26),
    "00101000": (1, 0, 7, 25),
    "00101001": (1, 1, 12, 28),
    "00101101": (0, 0, 5, 22),
    "00101110": (0, 0, 4, 22),
    "00110110": (1, 1, 10, 26),
    "00110111": (1, 1, 10, 27),
    "00111110": (1, 0, 7, 26),
    "01000000": (1, 0, 7, 24),
    "01000011": (0, 0, 8, 23),
    "01000111": (0, 0, 8, 21),
    "01001000": (0, 0, 4, 21),
    "01001010": (0, 1, 10, 23),
    "01001011": (0, 0, 5, 21),
    "01001111": (1, 1, 10, 24),
    "01010010": (0, 0, 8, 22),
    "01010111": (1, 1, 13, 25),
    "01011110": (0, 0, 10, 22),
    "01101000": (1, 0, 13, 25),
    "01101001": (1, 1, 13, 28),
    "01101110": (0, 1, 9, 22),
    "01110000": (1, 0, 1, 24),
    "01110100": (0, 1, 6, 21),
    "01110110": (1, 1, 13, 26),
    "01111000": (0, 0, 1, 21),
    "01111011": (0, 0, 7, 21),
    "01111110": (1, 0, 13, 26),
    "01111111": (1, 0, 0, 24),
    # Longer bracket runs, all on the second separator.  The first sweep
    # stopped at 13 for no better reason than that it was enough; these need
    # 14 to 22, and the axis is now taken to exhaustion rather than to a cap
    # -- see the note below on where the columns freeze.
    "00000111": (1, 0, 19, 30),
    "00010110": (1, 1, 16, 26),
    "00011111": (1, 0, 17, 28),
    "01000001": (1, 0, 21, 30),
    "01010110": (1, 1, 14, 26),
    "01100000": (1, 0, 17, 27),
    "01100001": (1, 0, 21, 28),
    "01100111": (1, 0, 17, 25),
    "01101111": (1, 0, 22, 28),
    # The one entry whose suffix is not a plain bracket run.  Nothing else
    # reaches this pair -- not the scans, not the column search, not the
    # parked search.
    "01101101": (2, 0, "[[<[<[[[[[[[[[", 22),
    # Reached by the three added separators; see the _SEPS note.
    "00000010": (3, 0, 20, 27),
    "00000100": (2, 0, 14, 26),
    "00001001": (2, 0, 19, 28),
    "00001011": (2, 0, 21, 28),
    "00001101": (2, 0, 11, 24),
    "00010000": (3, 0, 20, 29),
    "00010011": (2, 0, 3, 21),
    "00011010": (2, 0, 13, 27),
    "00011011": (2, 0, 15, 24),
    "00011100": (3, 1, 10, 27),
    "00011101": (2, 0, 7, 24),
    "00100000": (3, 1, 15, 27),
    "00100011": (2, 0, 1, 21),
    "00100100": (3, 0, 12, 29),
    "00100101": (2, 0, 13, 26),
    "00100111": (2, 0, 3, 23),
    "00101010": (2, 1, 13, 24),
    "00101011": (2, 1, 9, 23),
    "00101100": (2, 0, 0, 21),
    "00101111": (2, 0, 7, 21),
    "00110001": (3, 0, 1, 24),
    "00110010": (3, 0, 1, 22),
    "00110100": (3, 1, 12, 24),
    "00110101": (3, 1, 6, 26),
    "00111000": (3, 1, 13, 29),
    "00111001": (3, 0, 1, 26),
    "00111010": (2, 0, 9, 25),
    "00111011": (2, 0, 14, 27),
    "00111101": (2, 1, 14, 25),
    "01000010": (2, 0, 3, 22),
    "01000101": (2, 0, 11, 25),
    "01000110": (2, 0, 14, 25),
    "01001001": (2, 0, 10, 23),
    "01001100": (3, 0, 24, 30),
    "01001101": (2, 0, 9, 24),
    "01001110": (3, 1, 22, 32),
    "01010001": (2, 0, 9, 22),
    "01010011": (4, 0, 16, 26),
    "01010100": (3, 0, 21, 28),
    "01011000": (3, 0, 24, 28),
    "01011001": (3, 0, 1, 28),
    "01011011": (2, 1, 11, 24),
    "01011100": (3, 0, 22, 28),
    "01011101": (4, 0, 10, 22),
    "01100010": (2, 0, 11, 22),
    "01100011": (3, 1, 10, 28),
    "01100100": (2, 0, 7, 23),
    "01100101": (2, 0, 13, 25),
    "01101010": (2, 0, 19, 27),
    "01101011": (2, 1, 12, 24),
    "01101100": (2, 1, 17, 30),
    "01110001": (3, 0, 17, 28),
    "01110010": (2, 0, 1, 22),
    "01110011": (3, 1, 15, 28),
    "01110101": (4, 0, 14, 23),
    "01111001": (4, 0, 15, 23),
    "01111010": (2, 0, 13, 23),
    "01111100": (2, 1, 19, 30),
    "01111101": (2, 0, 0, 22),
}

_PLANS: dict[int, dict[str, _Staging]] = {
    2: _TWO_INPUT_PLAN,
    3: _THREE_INPUT_PLAN,
}


def _staged(truth_table: str, n: int) -> str | None:
    """Build from :data:`_PLANS` without searching, or None if unplanned.

    The plan is keyed by the lexicographically smaller of the table and its
    complement, since the pair shares a staging.  None rather than an
    exception on a miss, so the caller falls through to the searches and
    coverage cannot regress.
    """
    complement = "".join(str(1 - int(c)) for c in truth_table)
    plan = _PLANS.get(n, {}).get(min(truth_table, complement))
    if plan is None:
        return None
    sep_index, settle, suffix, acc = plan
    j = _embed(n, settle=settle, sep=_SEPS[sep_index])
    _clamp(j)
    _walk_to(j, _BASE - 1)
    # A count is the common case -- a plain bracket run, which the ``<``
    # terminates so the pointer lands where the endgame expects.  A literal
    # string is the escape hatch for the one staging a run cannot express.
    j.emit("[" * suffix + "<" if isinstance(suffix, int) else suffix)
    _clamp(j)
    hit = _try_print(j, truth_table, acc)
    return hit.template() if hit is not None else None


def _lift_leaves_name_order(essential: list[int], n: int) -> bool:
    """Whether lifting would emit the ``{Xi}`` out of ascending order.

    :func:`_lift` appends the ignored inputs after the solved template, so
    the result is still sorted when every ignored index is above every
    essential one -- ``{X0}{X1}`` then ``{X2}``.  It is only when an ignored
    index sits *below* an essential one that the append leaves sequence.
    """
    ignored = [i for i in range(n) if i not in essential]
    return bool(ignored and essential and min(ignored) < max(essential))


def _lift(template: str, essential: list[int], n: int) -> str:
    """Renumber a smaller table's placeholders back onto the wider arity.

    The inner solve used ``{X0}..{Xk-1}``, which correspond to the original
    inputs listed in ``essential``.  The renaming is done in a single pass, so
    a rename cannot collide with a placeholder it has not rewritten yet.

    Every input the function ignores still needs a placeholder, or the harness
    would have a bit with nowhere to put it.  Those go on the end: the fill is
    two characters whichever bit it is, so they cannot make the program's
    length depend on the inputs, and by then the digit has been printed -- the
    ``.`` has already run -- so whatever they do to the tape cannot matter.
    """
    rename = {f"X{slot}": f"X{i}" for slot, i in enumerate(essential)}
    lifted = re.sub(
        r"\{(X\d+)\}",
        lambda m: "{" + rename[m.group(1)] + "}",
        template,
    )
    ignored = "".join("{X" + str(i) + "}" for i in range(n) if i not in essential)
    return lifted + ignored


@cache
def minifuck(truth_table: str) -> str:
    """Build a Minifuck template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Minifuck has no usable input command, so this is a parameterized
    generator: the template's ``{Xi}`` placeholders become ``[<`` for a one
    and ``xx`` for a zero -- equal width, so no instantiation leaks its
    inputs through its length -- and the harness instantiates one program per
    input combination.

    The emitted program embeds each input once, computes the table in cells
    past the pool, relays the answer into the *pointer* (values cannot travel
    left, but the pointer can), and prints one ASCII digit.  Every step is
    simulated against all ``2**n`` rows as it is emitted, and a
    :class:`ValueError` is raised rather than returning a program that has
    not been seen to print the table.

    Cached, because at three inputs the simulated search is what this module
    costs -- seconds to tens of seconds a table, against effectively zero to
    *run* the program it returns.  Two inputs no longer pay that: they are
    derived from :data:`_TWO_INPUT_PLAN`, and all sixteen build in well under
    a second together.  The build is deterministic in ``truth_table`` and the
    result is an immutable string, so repeat calls are free either way.
    """
    n = _validate_truth_table(truth_table)
    want = tuple(int(c) for c in truth_table)

    # A table that ignores some of its inputs is a *smaller* table wearing
    # extra ones, so solve it at the arity it actually uses and renumber the
    # placeholders back.  This is the part of the construction that composes:
    # what it costs depends on the essential inputs, not on ``n``, so a wide
    # table with a narrow core is as cheap as that core.
    essential = _essential_inputs(truth_table, n)
    if len(essential) < n:
        # Projecting is much the cheaper route, but it emits the ignored
        # inputs after the ``.``, which leaves name order whenever an ignored
        # index sits below an essential one.  ``_embed`` already lays every
        # slot down in ascending order, so solving at the *full* arity is
        # in-order by construction -- try it first for exactly the tables the
        # lift would disorder, and only when it is the cheap closed-form
        # path.  A table with two or more essential inputs is not: measured
        # at n == 3, ``00000101`` runs the searches for 132 seconds and still
        # fails, against seconds to project.  Coverage comes first, so a miss
        # here falls through to the projection rather than raising.  The
        # attempt is capped at the fixed-cell lookup because that is where
        # every table it wins is won; letting it run the column search only
        # adds about five seconds to the tables it cannot build anyway.
        if _lift_leaves_name_order(essential, n):
            if len(essential) <= 1:
                in_order = _degenerate(truth_table, n, fixed_cells_only=True)
                if in_order is not None:
                    return in_order
            reconverged = _reconverged(truth_table, essential, n)
            if reconverged is not None:
                return reconverged
        inner = minifuck(_project(truth_table, essential, n))
        return _lift(inner, essential, n)

    # At most one essential input means a constant or a (negated) projection,
    # and the embed already holds every one of those as a column -- so the
    # answer is a cell lookup rather than a search.
    if len(essential) <= 1:
        degenerate = _degenerate(truth_table, n)
        if degenerate is not None:
            return degenerate

    # A planned staging is the cheapest route by far, so it goes first.  At
    # two inputs the plan is complete and no search ever runs; at three it
    # covers all 109 complement pairs, and a miss at another arity falls through to the
    # searches below.
    derived = _staged(truth_table, n)
    if derived is not None:
        return derived

    frontier = _BASE + n * _SPAN + 6

    # The scans first, across *both* separators, because they are by far the
    # cheapest route and a good share of tables land in one of them: the
    # embed's carry chain computes AND, NOR and XOR as a byproduct, so the
    # answer is often already sitting in a cell.  Interleaving them with the
    # searches (one separator fully, then the next) made tables that only the
    # second separator's scan reaches pay for three failed searches first --
    # measured at 69-82s each, against about 35s for the searches that do hit.
    for sep in _SCAN_SEPS:
        base = _embed(n, sep=sep)
        _clamp(base)
        for acc in range(9, frontier):
            hit = _try_print(base, truth_table, acc)
            if hit is not None:
                return hit.template()

    for sep in _SCAN_SEPS:
        # Otherwise search for the answer column outright.  The search has to
        # launch from the frontier, with the pointer already in the data: a
        # depth-``d`` walk from the origin never reaches cell ``_BASE``, so
        # every state it could see is input-independent.
        for park in range(_BASE - 2, _BASE + 2 * n + 4):
            probe = _embed(n, sep=sep)
            _clamp(probe)
            try:
                _walk_to(probe, park)
            except ValueError:
                continue
            found = _find_column(probe, want, frontier + 8, _COLUMN_DEPTH)
            if found is None:
                continue
            code, _cell = found
            probe.emit(code)
            _clamp(probe)
            for acc in range(9, frontier + 8):
                hit = _try_print(probe, truth_table, acc)
                if hit is not None:
                    return hit.template()

    # Last, and only if everything cheaper failed: park the pointer on the
    # answer as part of what is searched for, so no walk intervenes between
    # producing the column and reading it -- a walk back would re-cross, and
    # so change, that very cell.  This is the most expensive route, and it
    # earns its place at n == 2 (it is the only one reaching the XOR family)
    # while contributing no hits at all in an n == 3 sample, so it goes last.
    for sep in _SCAN_SEPS:
        for code, _cell in _find_parked(
            _embed(n, settle=_SETTLE, sep=sep),
            want,
            frontier + 8,
            _PARKED_DEPTH,
            _PARKED_LIMIT,
        ):
            probe = _embed(n, settle=_SETTLE, sep=sep)
            probe.emit(code)
            _clamp(probe)
            for acc in range(9, frontier + 8):
                hit = _try_print(probe, truth_table, acc)
                if hit is not None:
                    return hit.template()

    raise ValueError(f"the Minifuck boolean generator could not build {truth_table!r}")
