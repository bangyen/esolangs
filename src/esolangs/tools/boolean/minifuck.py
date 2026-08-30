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
makes a table build, and that choice is **derived, not stored**: the product
is small enough to walk, so :func:`_derive_staging` enumerates it in a fixed
order and takes the first entry that prints.  Each candidate is run and its
rows compared against the table, so nothing is accepted on a recorded claim.
The one exception is a single three-input table whose suffix no bracket run
spells; see :data:`_EXCEPTIONS`.

The selection rule is the load-bearing part, and it is why the enumeration
tests rather than predicts: the accumulator that works is the one whose
column reads correctly **at the read**, not the cell holding the answer
beforehand.  Those differ, because the walk out applies the running
prefix-XOR -- an AND column can arrive as a constant, and XOR can arrive as a
projection.  Choosing pre-walk covers 10 of the 16 two-input tables and looks
nearly right, which is the trap.

A table and its complement share a staging: the endgame tries both read
polarities and prints ``NOT(v XOR cell7)``, so the complement costs nothing.

**Coverage.**  Every table at ``n <= 3`` builds from a staging, with no
search: 16 of 16 at two inputs, 256 of 256 at three.  All but one pair are
derived, and the derivation is done for a whole arity at a time -- measured,
0.9s for two inputs and 15s for three, against minutes if each table sweeps
for itself.  So the first three-input table costs the arity and the other
255 are free; that is the trade deriving makes against storing.  Wider tables
fall through to the searches below, which is why those remain -- a missing
staging degrades rather than raises.
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
from collections.abc import Callable, Iterator
from functools import cache

from esolangs.tools.boolean.helpers import _validate_truth_table, read_at

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
# degenerate path and the fallback searches); the rest are reached by the
# staging enumeration, so adding one costs those routes nothing.
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

# Depth cap for the column search, a joint search over 2**n machines whose
# cost is exponential in the cap; this is the smallest value covering every
# two-input table.  (The pool no longer has one: see :data:`_POOL_CODES`.)
_COLUMN_DEPTH = 13

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


# The pool codes, five written down and the rest derived.
#
# Setting the pool is not a search: across every table at ``n <= 3`` the
# breadth-first search this replaced returned one of exactly ten strings, and
# trying those in turn reproduces its answer on every call the generator makes
# -- a code wherever it found one, and none where it found none.  Each
# candidate is still checked against the same acceptance test the search
# applied, so a code is accepted on exactly the evidence it always was.
#
# A lookup keyed on ``(cell7, walk_out)`` would *not* work, which is why this
# is a list tried in turn rather than a table: the same pair takes different
# codes, and sometimes none, depending on the state the staging leaves behind.
#
# **Why five and two rather than ten.**  Each code serves exactly one
# orientation -- none answers both ``cell7`` values -- and they come in mirror
# pairs, one code answering a state at ``cell7 == 0`` exactly where its
# partner answers the same state at ``cell7 == 1``.  Mechanically the mirror
# is only "flip cell 7": run a pair on one state and the two tapes agree
# everywhere else.  So the ``cell7 == 1`` half is generated by appending a
# flip, and only the ``cell7 == 0`` codes and the flips are written down.
#
# Two flips suffice for the four pairs that have one, which is the fact that
# makes this worth doing: ``[[[[<`` derives the partners of the two codes
# ending at cell 5, and ``[[[[[[<`` those of the two ending at cell 4.  The
# fifth pair is not derived and does not need to be -- crossing all five codes
# with both flips already covers every call site the ten strings answered.
#
# The flips are not interchangeable, and a *uniform* rule does not exist: the
# codes finish at four different pointer positions (1, 2, 4, 5), so "flip cell
# 7 from where I stopped" is a different string depending on where that is.
# Nor can the pointer be normalised first, and the reason says what a pool
# code is.  A suffix landing every code on one cell does exist -- ``<<<<<``
# drives all ten to cell 0, and ``<`` never writes -- but it destroys them:
# 16754 of the 16758 answered call sites are lost.  The walk out to the
# accumulator is ``[x`` repeated from wherever the code stopped, and every
# ``[x`` rewrites the cell it crosses, so moving the end left lengthens the
# walk and scribbles over the pool just set.  Measured on one site: the tape
# at the end of the code is identical either way, but a 3-step walk leaves
# ``0011000`` and an 8-step walk leaves ``0101110``.  A pool code therefore
# sets the pool *and* stops where the remaining walk will preserve it, and the
# four end positions are each paired with the walk lengths they must survive.
#
# The candidates are ordered shortest first, so the emitted program is no
# longer than before -- measured, no template grows and two shrink.
#
# The list is deliberately not minimal.  Measured over a build of both arities
# -- 34510 calls, 31 of which find no code -- every one of the ten strings
# gets used, four serving the staged route and the rest only the degenerate
# and reconverged ones.  But "used" is not "needed": dropping any single one
# breaks nothing, not because they cover for each other (six of them uniquely
# answer 40 of the 16766 call sites) but because **a missing pool is not
# fatal** -- ``_endgame`` raises, ``_try_print`` treats it as one failed
# read/orientation, and another accumulator answers the table.  Cutting to the
# four high-coverage codes takes the calls finding nothing from 31 to 437 and
# still builds every table.
_POOL_SETTERS = (
    "[[[<[<<<<",
    "[<[[[<[<[<",
    "[<[<[[[<[<[<",
    "[<<[<[<[[[<[<",
    "[<[<[<<[[[<[[<<<",
)

# What turns a pool setter into its ``cell7 == 1`` mirror.  See above: one
# flip per end position among the pairs that have a partner.
_POOL_FLIPS = ("[[[[<", "[[[[[[<")

# Every candidate, shortest first.  Generated rather than written out, and
# ``dict.fromkeys`` rather than a set so the order does not depend on hashing.
_POOL_CODES = tuple(
    sorted(
        dict.fromkeys(
            (*_POOL_SETTERS, *(s + f for s in _POOL_SETTERS for f in _POOL_FLIPS))
        ),
        key=len,
    )
)


def _pool_reaches(j: _Joint, code: str, cell7: int, walk_out: int) -> bool:
    """Whether ``code`` leaves the pool correct once walked out.

    The pool must read ``0011000`` plus ``cell7`` at print time, and the walk
    out to the accumulator crosses it -- so what matters is the pool *after*
    that walk, not at the moment the code ends.
    """
    target = (*_POOL, cell7)
    probe = [m.copy() for m in j.ms]
    for char in code:
        for m in probe:
            m.exec(char)
    if any(m.dead or m.skip for m in probe):
        return False
    if len({m.ptr for m in probe}) != 1:
        return False
    steps = walk_out - probe[0].ptr
    if steps < 0:
        return False
    for _ in range(steps):
        for char in "[x":
            for m in probe:
                m.exec(char)
    for cell in range(8):
        col = {m.tape[cell] for m in probe}
        if len(col) != 1 or probe[0].tape[cell] != target[cell]:
            return False
    return True


def _find_pool(j: _Joint, cell7: int, walk_out: int) -> str | None:
    """Return a pool code for this orientation, or None if none fits."""
    for code in _POOL_CODES:
        if _pool_reaches(j, code, cell7, walk_out):
            return code
    return None


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


# The columns a degenerate table can be built from: a constant, one of the
# first two inputs, or one of their complements.  A table depending on at
# most one input is exactly one of these, which is why naming them is enough.
_DEGENERATE_COLUMNS = ("const1", "~b0", "b0", "const0", "~b1", "b1")


def _column_of(name: str, n: int) -> tuple[int, ...] | None:
    """Return the column ``name`` stands for, or None if this arity has no such bit.

    ``b1`` does not exist at one input, and it must come back as None rather
    than as some default: an all-zero stand-in would match wherever
    ``const0`` does, and the route would carry a duplicate cell that means
    nothing.
    """
    rows = range(2**n)
    if name in ("const0", "const1"):
        return tuple(int(name == "const1") for _ in rows)
    negated = name.startswith("~")
    bit = int(name.lstrip("~")[1:])
    if bit >= n:
        return None
    return tuple((((r >> (n - 1 - bit)) & 1) ^ negated) for r in rows)


@cache
def _degenerate_cells(n: int) -> dict[str, int]:
    """Find where the embed leaves the constants and the first two inputs.

    These were six written-down cell numbers, and the reason they were
    constant is also the reason they need not be written down: the carry
    chain preserves ``b0`` and ``b1`` individually before the prefix-XOR
    starts mixing, so the cells holding them can simply be *read off* the
    embedded tape.  Measured, this reproduces the six exactly at every arity
    the route serves.

    Later inputs are not separable here at any settle count -- the affine
    transform fixes which bits stay apart -- but a column search finds them
    in a fraction of a second, which is why the degenerate path still beats
    the ladder without being wholly search-free.

    Only the default settle count is meaningful: :func:`_degenerate` embeds
    with it, and re-crossing the region moves these columns elsewhere.
    """
    joint = _embed(n, sep=_SEP)
    _clamp(joint)
    wanted = {
        name: column
        for name in _DEGENERATE_COLUMNS
        if (column := _column_of(name, n)) is not None
    }
    found: dict[str, int] = {}
    for cell in range(1, _BASE + n * _SPAN + 8):
        column = joint.col(cell)
        for name, target in wanted.items():
            if name not in found and column == target:
                found[name] = cell
    return found


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
    candidates = list(_degenerate_cells(n).values())
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

    The read itself is :func:`read_at`, shared with
    :func:`permute_truth_table` -- a permutation is the case where every
    input is essential, so nothing is held back.
    """
    return read_at(truth_table, essential, n)


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
    the essential input lands on the cells :func:`_degenerate_cells` finds,
    and the fixed-cell lookup decides in a fraction of a second.  The
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
        setup: tuple[int, int, int, int] | None = None
        accumulators: tuple[int, ...] = tuple(_degenerate_cells(n).values())
    else:
        inner = _project(truth_table, essential, n)
        plan = _derive_staging(inner, 2)
        if plan is None:
            return None
        sep_index, settle, brackets, acc = plan
        # Every two-input staging is a plain bracket run; the literal-suffix
        # form is only used by the one stored three-input exception, and
        # replaying it here would need the walk this route does not make.
        if not isinstance(brackets, int):
            return None
        setup = (sep_index, settle, brackets, acc)
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
            sep_index, settle, brackets, _acc = setup
            for slot, i in enumerate(essential):
                j.emit_setter(i)
                j.emit("[x")
                if slot + 1 < len(essential):
                    j.emit(_SEPS[sep_index])
            # The staging's settle count, replayed the way ``_embed`` does
            # it: re-crossing the bit region advances the affine state, and
            # the accumulator was chosen against the state that produces.
            # The enumeration hands back ``settle == 1`` for AND and NAND,
            # and six three-input tables project onto one of those, so
            # ignoring the field would replay them against the wrong tape.
            for _ in range(settle):
                _clamp(j)
                _walk_to(j, _BASE - 1)
            _clamp(j)
            _walk_to(j, _BASE - 1)
            j.emit("[" * brackets + "<")
        _clamp(j)
        for acc in accumulators:
            hit = _try_print(j, truth_table, acc)
            if hit is not None:
                return hit.template()
    return None


# The staged construction: one ``(separator, settle, suffix, accumulator)``
# per complement pair, *derived* rather than stored.
#
# The embed leaves an affine picture -- every cell holds a linear form in the
# input bits plus the one nonlinear term the ``[`` cascade computes -- and a
# plain run of ``k`` brackets from ``_BASE - 1`` sweeps that picture forward,
# exposing a different function at each step.  So the whole problem is: pick
# the separator, the bracket count and the accumulator, then hand the result
# to the endgame every other route already uses.
#
# Which is small enough to *enumerate*.  :func:`_stagings` gives the order --
# 5 separators x 2 settle counts x 29 bracket counts x 26 accumulators -- and
# a table is built by the first entry that prints it, so no table of answers
# is needed.
#
# :func:`_derived_plans` runs that enumeration for a whole arity at once,
# which is what makes it affordable.  A staging is expensive to build and
# cheap to test against a table, so the loops go staging-major: one embed per
# (separator, settle), the bracket run extended one instruction at a time,
# and the endgame emitted once per (k, accumulator, read, orientation)
# whatever the table.  Measured, the whole three-input arity derives in 15s
# and two inputs in 0.9s; the table-major spelling of the same search costs
# minutes, because it rebuilds every staging once per table.
#
# Selection is on the accumulator's value **at the read**, not on the cell
# that holds the answer beforehand.  Those differ, because the walk out
# applies the running prefix-XOR: at ``acc = 22`` after separator 1, AND
# ``(0,0,0,1)`` arrives as the constant ``(1,1,1,1)``, and XOR ``(0,1,1,0)``
# arrives as ``b1``.  Choosing on the pre-walk column is what made an earlier
# version of this cover 10 of the 16 two-input tables rather than all of them.
# The enumeration sidesteps that trap by construction: it does not reason
# about which column *ought* to arrive, it emits the endgame and reads what
# the rows actually printed.
#
# A table and its complement share a staging, because the endgame tries both
# read polarities and both pool orientations and the printed digit is
# ``NOT(v XOR cell7)``, so the complement costs nothing to reach.  That is
# why the counts below are given in complement pairs.
_Staging = tuple[int, int, int | str, int]

# **Coverage, and the one table that must still be stored.**  The enumeration
# reaches 108 of the 109 non-degenerate three-input pairs and all 8 at two
# inputs.  The holdout is ``01101101`` / ``10010010``, and it is worth knowing
# why, because it was the hardest table here by some margin and the searches
# never built it at all -- both members raise after about 96 seconds.
#
# Its answer column is not scarce: 14375 of 804600 sparse suffixes leave it
# standing somewhere on the tape.  What is scarce is a staging that also
# *carries* it to the read, because the walk's prefix-XOR rewrites the very
# cell.  A pure bracket run never manages it -- which is exactly why the
# enumeration cannot reach it, every entry of :func:`_stagings` being a run --
# and the stored suffix interleaves two ``<`` into the run instead.
#
# The shape of that miss is worth recording so it is not re-run blind.  Unlike
# the tables the wider separator set closed, its answer *is* computed:
# ``01101101`` stands as a column at cell 24 under separator 2 at ``k == 15``.
# What fails is the carry -- no accumulator reads it intact, and from that
# staging it arrives as ``10011101`` or ``01100010``, neither the table nor
# its complement.  A sweep over 13 of the 15 (separator, settle) slices at
# ``k <= 40`` and every accumulator found no staging that delivers it; the two
# skipped slices scored worst on a cheap distance screen, and the five that
# scored best -- reaching Hamming distance 1 but never 0 -- were all covered
# and all missed.
#
# It is a gap in this family, not a wall: 180 of the 256 possible columns
# arrive across the family, and no affine invariant separates them from this
# one (all 255 parity masks checked), so nothing here forbids it.
#
# What closed the *other* gaps was not a better search but a wider separator
# set.  See the note on :data:`_SEPS`: the first two separators leave only 92
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
# redundant.  The deepest first hit the enumeration actually needs is
# ``k == 26`` at three inputs and ``k == 6`` at two, which is where
# :data:`_MAX_BRACKETS` comes from; stopping at 30 would have been a cap
# rather than a bound.
#
# The other two axes were *sampled* rather than exhausted and came back
# empty -- settle counts 3 to 5 and accumulators 36 to 47 reached nothing the
# shipped stagings did not.  That is evidence they are barren, not proof.
#
# **A simpler form was looked for and does not exist.**  This is what the
# enumeration replaced a stored table with, and not what it could have been:
# the wish was a *uniform* rule -- one staging, or at least one field fewer --
# even at the cost of longer programs.  Every version of that was measured and
# fails, which is why all four fields are still enumerated:
#
# * **One fixed staging: impossible**, and by counting rather than by search.
#   A staging offers one column per accumulator and orientation -- 52 slots
#   over the ranges used here -- but those collapse badly, because the walk's
#   prefix-XOR is many-to-one and different accumulators keep arriving at the
#   same column.  Measured over every staging in the family, **the best
#   single one delivers 13 pairs and the mean is 5.8**, against 109 to place.
#   So this is short by a factor of eight, not marginally.
# * **Two separators: 99 of 109**, and *not* for want of room -- re-running
#   with bracket counts to 70 and accumulators to 60 reaches the same 99.
#   The ten stragglers need a different separator, not a longer program.
#   This is why :func:`_stagings` walks all five.
# * **Dropping the settle field: 99 of 109.**  Ten pairs are reachable only
#   at ``settle == 1``, so the staging cannot shrink to three fields.
#
# Separator 0 is the one curiosity: no *three-input* table needs it, since
# separators 1 to 4 reach 108 of the 109 between them.  It is enumerated
# first anyway because it carries every two-input table on its own, and
# :data:`_SEP` and :data:`_SCAN_SEPS` use it.
#
# Two more things look removable and are not.  ``_SETTLE`` is unused by the
# enumeration but parameterises the parked search, which still serves
# ``n >= 4``; and the searches themselves are unreachable at ``n <= 3`` yet
# are what a wider table falls through to.  Neither is dead.

# The arities the enumeration covers.  Beyond three it is not that the
# enumeration fails but that it has not been shown to succeed, and a route
# that grinds through the whole product before giving up would be worse than
# the fall-through it replaces -- so the gate is explicit rather than
# implied by a miss.
_STAGED_ARITIES = (2, 3)

# How far the enumeration runs.  Both caps are the measured maximum over
# every table plus a margin, not guesses: sweeping to a bracket count of 30
# and an accumulator of 40, the deepest first hit at two inputs is
# ``(k=6, acc=20)`` and at three ``(k=26, acc=31)``.  Nothing is reached past
# those, so the sweep stops a little beyond them.
_MAX_BRACKETS = 28
_MAX_ACC = 34


def _stagings(n: int) -> Iterator[_Staging]:
    """Enumerate ``(separator, settle, bracket count, accumulator)`` in order.

    The order is what makes the derivation deterministic, and it is chosen so
    the cheap stagings come first: separator, then settle, then the bracket
    run, then the accumulator.  A table is built by the *first* of these that
    prints it, so this order -- not a stored table -- is what fixes which
    program each truth table gets.

    :func:`_derived_plans` does not call this: it interleaves the same four
    loops with the machines it is advancing, so that a bracket count costs one
    instruction rather than a rebuild.  This states the order those loops
    implement, and the test suite checks the two agree.

    ``n`` is unused, the enumeration being the same at every arity; it is
    taken so the caps could be made arity-dependent without changing callers.
    """
    del n
    for sep_index in range(len(_SEPS)):
        for settle in (0, 1):
            for brackets in range(_MAX_BRACKETS + 1):
                for acc in range(9, _MAX_ACC + 1):
                    yield sep_index, settle, brackets, acc


# The one table the enumeration cannot reach.  Its suffix interleaves two
# ``<`` into the bracket run, which no ``'[' * k`` spells, so no entry of
# :func:`_stagings` expresses it.  This is not a staging the sweep merely
# missed: pure bracket runs were taken to exhaustion for this pair over every
# separator, settle count and accumulator -- 13 of the 15 slices at
# ``k <= 40`` -- and none carries its column to the read.  The search that
# did find it ran for 29 minutes, which is why it is stored rather than
# derived.  See the note on :data:`_SEPS` and commit 89bcc12.
_EXCEPTIONS: dict[int, dict[str, _Staging]] = {
    3: {"01101101": (2, 0, "[[<[<[[[[[[[[[", 22)},
}


def _replay(truth_table: str, n: int, plan: _Staging) -> str | None:
    """Build one staging and return its template, or None if it does not print.

    The suffix is a bracket *count* for everything the enumeration produces --
    a plain run, which the ``<`` terminates so the pointer lands where the
    endgame expects -- and a literal string for the one stored exception.
    """
    sep_index, settle, suffix, acc = plan
    j = _embed(n, settle=settle, sep=_SEPS[sep_index])
    _clamp(j)
    _walk_to(j, _BASE - 1)
    j.emit("[" * suffix + "<" if isinstance(suffix, int) else suffix)
    _clamp(j)
    hit = _try_print(j, truth_table, acc)
    return hit.template() if hit is not None else None


@cache
def _derived_plans(n: int) -> dict[str, _Staging]:
    """Derive a staging for every table at this arity, in one pass.

    The whole arity is done at once because a staging is expensive to *build*
    and cheap to *test against a table*: the embed, the bracket run and the
    endgame do not depend on which table is wanted, and only the comparison
    at the very end does.  So the loops run staging-major -- one embed per
    ``(separator, settle)``, the bracket run extended one ``[`` at a time
    rather than rebuilt, and the endgame emitted once per
    ``(k, accumulator, read, orientation)`` -- and each printed column is
    looked up among the tables still wanting one.

    Doing it table-major instead re-derives the same stagings once per table
    and costs minutes rather than seconds, which is what an earlier version
    of this did.  The result is identical either way: a table is assigned the
    first staging in :func:`_stagings` order that prints it.

    Returns a mapping from truth table to staging.  A table that no staging
    reaches is simply absent, so the caller falls through to the searches.
    """
    if n not in _STAGED_ARITIES:
        return {}

    # What each printed column would answer.  A table and its complement
    # share a staging, so both spellings map to their own table and whichever
    # is reached first assigns both.
    wanted: dict[tuple[int, ...], list[str]] = {}
    for r in range(2 ** (2**n)):
        table = format(r, f"0{2**n}b")
        wanted.setdefault(tuple(int(c) for c in table), []).append(table)
    remaining = 2 ** (2**n)

    found: dict[str, _Staging] = {}
    for sep_index in range(len(_SEPS)):
        for settle in (0, 1):
            base = _embed(n, settle=settle, sep=_SEPS[sep_index])
            _clamp(base)
            _walk_to(base, _BASE - 1)
            run = base.fork()
            for brackets in range(_MAX_BRACKETS + 1):
                staged = run.fork()
                staged.emit("<")
                _clamp(staged)
                for acc in range(9, _MAX_ACC + 1):
                    for read in _READS:
                        for cell7 in (0, 1):
                            probe = staged.fork()
                            try:
                                _endgame(probe, acc, read, cell7)
                            except ValueError:
                                continue
                            printed = probe.printed()
                            if any(len(digit) != 1 for digit in printed):
                                continue
                            column = tuple(int(digit) for digit in printed)
                            for table in wanted.get(column, ()):
                                if table not in found:
                                    found[table] = (
                                        sep_index,
                                        settle,
                                        brackets,
                                        acc,
                                    )
                                    remaining -= 1
                    if not remaining:
                        return found
                # Extending the run is what makes this cheap: the next
                # bracket count is one instruction on from this one, not a
                # rebuild from the embed.
                run.emit("[")
    return found


def _derive_staging(truth_table: str, n: int) -> _Staging | None:
    """Return the staging that builds ``truth_table``, or None if none does.

    Every staging is accepted on the evidence of its own output -- the
    endgame is emitted and the rows are compared against the table -- so this
    needs no table of answers.  The enumeration order in :func:`_stagings` is
    the whole specification: it, and not a stored answer, decides which
    program a truth table gets.

    The stored exception is keyed by the lexicographically smaller of the
    table and its complement, since that pair shares a staging: the endgame
    tries both read polarities and prints ``NOT(v XOR cell7)``.
    """
    if n not in _STAGED_ARITIES:
        return None
    complement = "".join(str(1 - int(c)) for c in truth_table)
    exception = _EXCEPTIONS.get(n, {}).get(min(truth_table, complement))
    if exception is not None:
        return exception
    return _derived_plans(n).get(truth_table)


def _staged(truth_table: str, n: int) -> str | None:
    """Build from a derived staging without searching, or None if there is none.

    None rather than an exception on a miss, so the caller falls through to
    the searches and coverage cannot regress.
    """
    plan = _derive_staging(truth_table, n)
    return None if plan is None else _replay(truth_table, n, plan)


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
    derived from the staging enumeration, and all sixteen build in well under
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
