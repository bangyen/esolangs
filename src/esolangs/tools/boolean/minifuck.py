"""Boolean-function generator for Minifuck (parameterized convention).

Minifuck's only input is ``.`` reading a byte when the eight-cell pool is
zero.  This follows the parameterized convention described in
:mod:`esolangs.tools.boolean.parameterized`: the template's ``{Xi}``
placeholders are filled with ``[<`` (bit 1) or ``xx`` (bit 0), one program
per input combination.

That read *is* usable without destroying the pool, contrary to what this
docstring used to claim: a re-zero gadget after each read leaves the pool
input-independent while the bit survives as a pointer offset, and a prototype
swapping :func:`_embed` for such a reading prologue -- reusing everything
below it verbatim -- builds and verifies all four one-input and all sixteen
two-input tables with clean output.  The parameterized path is kept because
that prologue does not yet reach ``n == 3``, where the pointer must cross the
banked bits to leave the pool and ``[``'s skip desynchronizes the rows.  See
``docs/parameterized-input-conversion.md``.

``docs/walls.md`` records Minifuck as reaching only the four one-input
functions plus the eight 0-preserving two-input tables.  **That
characterization is about the runtime-read model and remains true as stated**
-- it does not carry over to embedded inputs, where every two-input table is
reachable, NAND, NOR and XNOR included.

The construction rests on four facts about the language, each checked against
the interpreter rather than argued from the spec:

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

Because that bookkeeping is affine but fiddly, nothing here is hand-tracked:
:class:`_Joint` runs all ``2**n`` instantiations in lockstep as the template
is emitted, every choice is made against the simulated truth, and
:func:`minifuck` raises rather than returning a program it has not seen
print the table.

**Coverage: every two-input table, and eight of the fourteen three-input
orbits.**  This is a *search* -- three routes across two embed separators --
so its reach is bounded by the depth caps below rather than by an argument.
Measuring by orbit rather than by sampling tables: the four degenerate orbits
are immediate, and AND3, majority, parity and one more build in 7-40 seconds.
The six that fail do so after about two minutes, and not for want of a
computable answer -- the column search finds the answer for all six in
seconds; it is the walk to an accumulator that washes it out.  See
``docs/walls.md``.

That makes this generator weaker than the repo's better ones, and the
comparison is worth stating: ``bfpda`` is a closed-form decision tree at any
arity, and ``wii2d`` *was* a capped search before it was replaced by a
construction (a Horner index chain plus a fold decode).  Whether Minifuck's
position-accumulation can be constructed the same way was investigated and
is, for now, answered no: the chain's doubling stage does not compose past
width four (48 configurations, depth 13), and even a chain that did would
still need a decode this language does not have, since wii2d's fold inverts
an accumulated *number* while the endgame below decodes a *bit*.
``docs/walls.md`` records both gaps, and the one mechanism that is disproved
outright rather than merely unfound.
"""

import re
from collections import deque
from collections.abc import Callable
from functools import cache
from typing import TypeVar

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["minifuck"]

# What an acceptance callback keeps: each search names its own result type,
# and returning None means "keep looking".
_Hit = TypeVar("_Hit")

# Where the embedded bits start.  The pool is cells 0..7, so the working area
# begins past it with a little room for the walk-in.
_BASE = 16

# What separates one embedded bit from the next.  A plain ``[x`` run leaves
# the prefix-XORs too correlated for the one-sided tests the endgame makes;
# the ``<`` steps back over a cell so the parities stay distinguishable.
_SEPS = ("[x<[x", "[x[x[x")
_SEP = _SEPS[0]

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


def _search(
    j: _Joint,
    accept: Callable[[list[_Sim], str], _Hit | None],
    maxlen: int,
) -> _Hit | None:
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
            if any(m.dead for m in new):  # pragma: no cover - see below
                # Unreachable from here: only a print kills a row, and the
                # alphabet this search explores has none.  Kept because the
                # prune is a property of the state, not of the alphabet, and
                # a search over ``.`` would need it.
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
    """
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
    for cell in range(8):
        if len(set(j.col(cell))) != 1:  # pragma: no cover - see below
            # Unreachable as things stand: ``_find_pool`` accepts a code
            # only after checking the pool *past* the walk out, which is
            # this same state.  Kept as the assertion that pairs the two --
            # the check there is on a simulated walk, and this one is on
            # what was actually emitted.
            raise ValueError(f"pool cell {cell} is input-dependent")
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


def _degenerate(truth_table: str, n: int) -> str | None:
    """Build a table depending on at most one input, without the ladder.

    Such a table is a constant, a projection, or a negated projection, and
    every one of those already stands as a *column* somewhere after the
    embed -- at a known cell for the first two inputs, and at a cheaply
    searched one beyond that.  So the whole construction is: find the cell
    holding the answer, then run the endgame on it.

    This is the piece that composes upward: a table with ``k`` essential
    inputs is a ``k``-input problem whatever its arity, so four of the
    fourteen three-input orbits are handled here for free.
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

    Cached, because that simulated search is what this module costs: about
    26s per two-input table, against effectively zero to *run* the program it
    returns.  The search is deterministic in ``truth_table`` and the result
    is an immutable string, so repeat calls are free.  Callers that build the
    same table more than once -- the test suite sweeps all sixteen two-input
    tables and separately spot-checks several of them -- pay the search once.
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
        inner = minifuck(_project(truth_table, essential, n))
        return _lift(inner, essential, n)

    # At most one essential input means a constant or a (negated) projection,
    # and the embed already holds every one of those as a column -- so the
    # answer is a cell lookup rather than a search.
    if len(essential) <= 1:
        degenerate = _degenerate(truth_table, n)
        if degenerate is not None:
            return degenerate

    frontier = _BASE + n * _SPAN + 6

    # The scans first, across *both* separators, because they are by far the
    # cheapest route and a good share of tables land in one of them: the
    # embed's carry chain computes AND, NOR and XOR as a byproduct, so the
    # answer is often already sitting in a cell.  Interleaving them with the
    # searches (one separator fully, then the next) made tables that only the
    # second separator's scan reaches pay for three failed searches first --
    # measured at 69-82s each, against about 35s for the searches that do hit.
    for sep in _SEPS:
        base = _embed(n, sep=sep)
        _clamp(base)
        for acc in range(9, frontier):
            hit = _try_print(base, truth_table, acc)
            if hit is not None:
                return hit.template()

    for sep in _SEPS:
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
    for sep in _SEPS:
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
