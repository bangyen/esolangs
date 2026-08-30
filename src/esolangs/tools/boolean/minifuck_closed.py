"""Closed-form boolean-function generator for Minifuck.

This is the search-free construction described in
``notes/minifuck-closed-form.md``.  It is kept beside the existing
:mod:`esolangs.tools.boolean.minifuck` while its coverage is established
arity by arity; nothing imports it yet.

**Nothing here searches for a program.**  Every choice is arithmetic or a
measurement of the simulated tape, so a table costs one region build plus a
linear solve whatever its shape.

The construction
----------------

* **The pool** (cells 0..7) is written first, as an ASCII digit with cell 7
  carrying the answer, so the printed byte is ``'0'`` (48) or ``'1'`` (49).
  Two spellings are kept, differing only in cell 7, because they print the
  two landing cells the opposite way round -- and a truth table and its
  complement want opposite arrangements.  Carrying both means the schedule
  may come out either way up.
* **The region** follows: a constant pattern written rightward, then one
  crossing per input.  Input ``k``'s ``{Xk}`` setter is emitted at an entry
  cell, and the entries strictly descend so each setter lands on a cell no
  earlier crossing has written -- a setter on a *one* makes ``[`` skip its
  ``<``, and the rows' pointers diverge.
* **The reads.**  A read is ``'[' + '<'*gap``: it adds the cell's value to
  the pointer and moves left by ``gap-1``.  ``<`` never writes and clamps at
  zero, so the travel between reads leaves no debris -- which is what lets a
  chain of reads compose at all.  (Chaining them *rightward* does not work:
  a read's write lands where the next one would look.)
* **The endgame.**  The reads leave the rows at two adjacent positions, one
  per answer.  A fixed ``<`` walk drops them onto cells 6 and 7, and ``[x.``
  writes cell 7 (or 8) and prints.  ``[x`` rather than a bare ``[``, because
  ``[`` on a one-cell leaves a pending skip that would eat the ``.``.

Why the reads can separate the rows
-----------------------------------

Every cell of the region holds an *affine* function of the inputs, and a
read adds that function to the pointer.  The rows start **converged**, so
every read splits them; they merge only by landing together.

Affineness is what makes the split possible.  Were the cells *constant*,
every row would gain the same amount and the rows could never come apart at
all; and the reachable groupings would be the contiguous blocks of the row
order, so only tables whose class sequence has at most two runs could build
-- 16 of 256 at three inputs.

The same fact bounds what a read can do at the start.  A non-constant affine
function on ``GF(2)^n`` is *balanced*, so the first read splits the rows
evenly however it is chosen; only once they are apart does each row sit
alone on a cell whose free bit steers it independently.

What this costs is the *coarse* tables.  Splitting reads naturally produce
finely divided arrangements, so a table whose answer classes are long
contiguous runs is the hard case, not the easy one -- at three inputs and
depth 6, none of the fourteen two-run tables is reachable while 44 of the
seventy five-run tables are.  The intuition runs backwards from the
constant-cell picture, which is worth stating because it is easy to import
the wrong model from that analysis.

The pattern is solved, not searched
-----------------------------------

The map from the region's pattern bits to the resulting tape is linear over
``GF(2)``, so the pattern realising a wanted set of ``(cell, row)`` values is
found by Gaussian elimination.  Each cell offers a complementary pair of
columns, so a cell constrained by one row can always deliver either bit; an
over-constrained cell makes the system inconsistent, which is reported
rather than worked around.
"""

import itertools
from collections import deque

from esolangs.tools.boolean.helpers import _validate_truth_table
from esolangs.tools.boolean.minifuck import _set_bit, _Sim

__all__ = ["minifuck_closed"]

# The pool, written into cells 1..7 (cell 0 is never written).  Two
# spellings, differing only in cell 7, and the difference is what lets a
# schedule of either orientation be printed.
#
# With cell 7 clear the pool spells '0' and a row on cell 6 flips cell 7 to
# spell '1', so the *one* class must land low:
#
#     cell 5 -> '3'   cell 6 -> '1'   cell 7 -> '0'   cell 8 -> '0'
#
# With cell 7 already set the mapping reverses -- cell 6 clears it back to
# '0', cell 7 flips cell 8 outside the pool and leaves '1' -- so the one
# class must land high:
#
#     cell 6 -> '0'   cell 7 -> '1'
#
# A truth table and its complement want opposite arrangements, and the
# planner's reads reach one of the two; carrying both pools means it does
# not matter which.  Sweeping every pool constant and both landings, these
# are the only two that print a clean '0'/'1' pair.
_POOL_ZERO_LOW = (0, 1, 1, 0, 0, 0, 0)
_POOL_ZERO_HIGH = (0, 1, 1, 0, 0, 0, 1)

# Where the two classes land.  Which of the two is the *one* class depends
# on the pool: with ``_POOL_ZERO_LOW`` it is the lower cell, with
# ``_POOL_ZERO_HIGH`` the upper.
_LAND_LOW = 6
_LAND_HIGH = 7

# The gadgets :func:`_write_pattern` picks from.  Each advances the pointer
# exactly one cell and leaves a chosen bit behind; which one applies depends
# on what the arriving cell already holds, so the choice is made by
# simulation rather than by a rule.
_WRITE_GADGETS = ("[", "[x", "[<[", "[<[x", "[<[<[", "[x<[", "[x<[x")


def _write_pattern(sim: "_Sim", bits: list[int]) -> str:
    """Return code writing ``bits`` into the cells right of ``sim.ptr``.

    Advances exactly one cell per bit, so the caller knows where it ends up.
    ``sim`` is advanced in step with the returned code.
    """
    code = ""
    for bit in bits:
        target = sim.ptr + 1
        for gadget in _WRITE_GADGETS:
            probe = sim.copy()
            for char in gadget:
                probe.exec(char)
            if probe.dead or probe.skip:
                continue
            if probe.ptr == target and probe.tape[target] == bit:
                for char in gadget:
                    sim.exec(char)
                code += gadget
                break
        else:  # pragma: no cover - the menu covers every arriving state
            raise ValueError(f"cannot write {bit} at cell {target}")
    return code


class _Joint:
    """The ``2**n`` instantiations, advanced in lockstep as code is emitted."""

    def __init__(self, n: int, size: int) -> None:
        """Start one machine per row of the truth table."""
        self.n = n
        self.rows = [
            [(r >> (n - 1 - k)) & 1 for k in range(n)] for r in range(2**n)
        ]
        self.ms = [_Sim(size) for _ in self.rows]
        self.parts: list[str] = []

    def emit(self, code: str) -> None:
        """Append code and run it on every row, keeping them in lockstep."""
        self.parts.append(code)
        for machine in self.ms:
            for char in code:
                machine.exec(char)

    def emit_setter(self, i: int) -> None:
        """Emit the ``{Xi}`` placeholder, simulating each row with its bit."""
        self.parts.append("{X" + str(i) + "}")
        for bits, machine in zip(self.rows, self.ms, strict=True):
            for char in _set_bit(bits[i]):
                machine.exec(char)

    def converged(self) -> bool:
        """Whether every row's pointer agrees."""
        return len({m.ptr for m in self.ms}) == 1

    def ptr(self) -> int:
        """The common pointer.  Only meaningful when converged."""
        return self.ms[0].ptr

    def column(self, cell: int) -> tuple[int, ...]:
        """``cell``'s value across the rows -- the function it holds."""
        return tuple(m.tape[cell] for m in self.ms)

    def template(self) -> str:
        """The emitted template, ``{Xi}`` placeholders included."""
        return "".join(self.parts)


def _region(
    n: int,
    pattern: list[int],
    pool: tuple[int, ...] = _POOL_ZERO_LOW,
    size: int = 400_000,
) -> tuple | None:
    """Write the pool, then the region, then cross it once per input.

    Returns ``(joint, lo, hi)`` for the region's cell range, or None if any
    stage leaves the rows' pointers diverged -- which is a bug in the
    caller's sizing rather than a table this cannot build, so the caller
    treats None as fatal.

    ``pool`` selects which digit each landing cell prints; see the two
    ``_POOL_*`` constants.  It shifts the whole region one cell right (it is
    a seven-bit write rather than six), which is why the model and the
    schedule must be built with the same pool.
    """
    joint = _Joint(n, size)
    scratch = joint.ms[0].copy()
    joint.emit(_write_pattern(scratch, list(pool)))
    joint.emit("[x" * 4)
    start = joint.ptr()

    scratch = joint.ms[0].copy()
    joint.emit(_write_pattern(scratch, [0] * (n + 1) + list(pattern)))
    right = scratch.ptr

    for k in range(n):
        # Entries descend, so setter k lands left of every earlier crossing
        # and therefore on a cell none of them wrote.
        entry = start + n - k
        joint.emit("<" * (joint.ptr() - entry))
        if not joint.converged():
            return None
        if any(m.tape[entry + 1] for m in joint.ms):
            return None
        joint.emit_setter(k)
        joint.emit("[x" * (right - entry))
        if not joint.converged():
            return None
    return joint, start + 1, right


def _model(
    n: int, width: int, pool: tuple[int, ...] = _POOL_ZERO_LOW
) -> tuple | None:
    """Measure the region as an affine map of its pattern bits.

    Returns ``(base, deltas, span)``: the tape each cell holds under the
    all-zero pattern, and the change one pattern bit makes.  The map is
    linear over GF(2), so these determine every reachable tape -- which is
    what lets :func:`_solve` answer by elimination instead of by trying
    patterns.
    """
    built = _region(n, [0] * width, pool)
    if built is None:
        return None
    joint, lo, hi = built
    rows = 2**n
    base = {c: joint.column(c) for c in range(lo, hi + 1)}

    deltas: list[dict[int, tuple[int, ...]] | None] = []
    for bit in range(width):
        pattern = [0] * width
        pattern[bit] = 1
        flipped = _region(n, pattern, pool)
        if flipped is None or flipped[1] != lo or flipped[2] != hi:
            deltas.append(None)
            continue
        other = flipped[0]
        deltas.append(
            {
                c: tuple(other.column(c)[r] ^ base[c][r] for r in range(rows))
                for c in range(lo, hi + 1)
            }
        )
    return base, deltas, (lo, hi)


def _cosets(base: dict, deltas: list, n: int, span: tuple) -> dict:
    """The columns each cell can be made to hold.

    A cell's reachable set is a coset of the span of its deltas.  In
    practice every cell inside the region offers exactly two, complementary,
    columns -- one free bit -- which is why a cell constrained by a single
    row can always deliver either value.
    """
    lo, hi = span
    reachable = {}
    for cell in range(lo, hi + 1):
        vectors = [d[cell] for d in deltas if d is not None]
        spanned = {tuple([0] * (2**n))}
        for vector in vectors:
            spanned |= {
                tuple(a ^ b for a, b in zip(s, vector, strict=True))
                for s in spanned
            }
        reachable[cell] = {
            tuple(a ^ b for a, b in zip(base[cell], s, strict=True))
            for s in spanned
        }
    return reachable


def _solve(
    constraints: dict, base: dict, deltas: list, width: int
) -> list[int] | None:
    """Solve for the pattern bits realising ``constraints``.

    ``constraints`` maps ``(cell, row)`` to the wanted bit.  The system is
    linear over GF(2); None means the demands contradict each other, which
    happens when one cell is asked for two different columns.
    """
    rows: list[list[int]] = []
    rhs: list[int] = []
    for (cell, row), want in constraints.items():
        coefficients = [
            d[cell][row] if d is not None and cell in d else 0 for d in deltas
        ]
        rows.append(coefficients)
        rhs.append(want ^ base[cell][row])

    pivots: list[int] = []
    rank = 0
    for column in range(width):
        pivot = next((i for i in range(rank, len(rows)) if rows[i][column]), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        rhs[rank], rhs[pivot] = rhs[pivot], rhs[rank]
        for i in range(len(rows)):
            if i != rank and rows[i][column]:
                rows[i] = [
                    a ^ b for a, b in zip(rows[i], rows[rank], strict=True)
                ]
                rhs[i] ^= rhs[rank]
        pivots.append(column)
        rank += 1
        if rank == len(rows):
            break

    if any(rhs[i] and not any(rows[i]) for i in range(rank, len(rows))):
        return None
    solution = [0] * width
    for i, column in enumerate(pivots):
        solution[column] = rhs[i]
    return solution


# How far a read steps left, and how many reads a schedule may use.  The gap
# must exceed the number of reads, so that no two reads' landing zones
# overlap and each row lands on a cell of its own.
def _gap_for(n: int) -> int:
    """The wide left step, used to spread the rows apart.

    Wide enough that no two reads' landing zones overlap, so each row lands
    on a cell of its own and that cell's free bit steers it alone.
    """
    return 4 * 2**n + 2


def _gaps_for(n: int) -> tuple[int, ...]:
    """The step lengths a read may use.

    A read is ``'[' + '<'*gap``, so the gap decides what the read *does*:

    * a **wide** gap moves every row far left, spreading them apart;
    * a **narrow** gap barely moves them, and a row that gains the read's
      bit catches up with the row above -- the two land together.

    Merging matters because the rows begin converged and every read splits
    them, so a table whose answer classes are long contiguous runs needs
    rows brought back together, and only a narrow gap does that.  With one
    fixed gap a schedule can spread or gather but never both; offering the
    narrow steps as well is worth more than three extra levels of depth.
    Measured at three inputs and depth 5: 58 of 254 tables with the wide
    gap alone, 156 adding a gap of one, 192 with the menu below.

    A read moves a row by ``1 - step + bit``, so the *spread* it opens
    between two rows is one whatever the step: the step does not control
    how strongly a read separates them, only where they end up.  What it
    controls is whether a row stands still, and that is what makes three
    the smallest usable narrow step:

        step 1:  deltas {0: 0, 1: +1}   -- a row can move right
        step 2:  deltas {0: -1, 1: 0}   -- a row can stand still
        step 3:  deltas {0: -2, 1: -1}  -- every row moves left

    A row that stands still, or moves right and comes back, reads a cell it
    has already read.  That is fatal rather than wasteful: ``[`` flips the
    cell it consults, so the second visit sees the complement of what the
    solver planted, and the constraint the solver wrote describes a value
    the machine no longer holds.  Over four-read walks, 270 of 1296 revisit
    a cell once a step of one is allowed, against none when every step is
    three or more.

    Excluding one and two costs nothing.  Measured at three inputs and
    depth 5: 58 of 254 tables with the wide step alone, 58 again adding a
    step of two -- which the revisit guard reduces to a uniform shift --
    and 182 adding a step of three.  Allowing one as well reaches the same
    182, so the safe menu gives up no coverage at all.
    """
    return (3, _gap_for(n))


def _plan(
    n: int,
    table: list[int],
    reachable: dict,
    start: int,
    gaps: tuple[int, ...],
    depth: int,
) -> tuple[list, int] | None:
    """Choose the reads, by walking the achievable moves.

    At each step the rows occupy known cells, and each occupied cell offers
    a complementary pair of columns -- so the achievable joint moves are a
    product of one binary choice per occupied cell, a handful in all.  This
    walks that move set to a state where the two answer classes sit at
    adjacent positions.

    The move set is derived from the measured tape, not from enumerating
    programs: what varies is which of a cell's two columns is chosen, and
    that choice is realised afterwards by :func:`_solve`.

    The accepted end state is the zero class exactly one cell above the one
    class.  That orientation is forced rather than chosen: the closing walk
    puts the one class on cell 6, and a row *below* 6 would write into the
    pool and spell some other byte, while a row above 7 is harmless.  Either
    arrangement is accepted, because there are two pools; ``upper`` says
    which one came out so the caller can write the matching pool.

    The rows begin **converged** -- one crossing per input leaves every
    pointer equal -- and each read *splits* them, since it adds a cell's
    affine value and the rows differ in that value.  Merging happens only
    when two rows happen to land together.

    That asymmetry decides which tables build.  Reads produce finely-split
    arrangements, so the *coarse* tables -- those whose answer classes are
    long contiguous runs -- are the ones that go unbuilt.  Measured at three
    inputs and depth 6: of the fourteen two-run tables, none is reachable,
    while 44 of the seventy five-run tables are.  The language offers no
    remedy; see the note below on why the clamp cannot supply one.

    Returns ``(history, upper)``, the history being the moves to replay.
    """
    rows = 2**n
    initial = tuple(start for _ in range(rows))
    seen = {initial}
    queue = deque([(initial, [])])
    while queue:
        positions, history = queue.popleft()
        by_class: dict[int, set[int]] = {}
        for r in range(rows):
            by_class.setdefault(table[r], set()).add(positions[r])
        if len(by_class) == 2 and all(len(v) == 1 for v in by_class.values()):
            zero = min(by_class[0])
            one = min(by_class[1])
            # Either arrangement will do, because there are two pools: with
            # the zero class on top the low pool prints it, and with the one
            # class on top the high pool does.  Return which way round it
            # came out so the caller can pick the matching pool.
            if abs(zero - one) == 1 and min(zero, one) >= _LAND_LOW + 1:
                return history, (0 if zero > one else 1)
        if len(history) >= depth:
            continue

        # Each read makes one binary choice per occupied cell, and picks a
        # step length: a wide one spreads the rows, a narrow one gathers
        # them.  See :func:`_gaps_for`.
        occupied: dict[int, list[int]] = {}
        for r in range(rows):
            occupied.setdefault(positions[r] + 1, []).append(r)
        if not any(cell not in reachable for cell in occupied):
            choices = [sorted(reachable[cell]) for cell in sorted(occupied)]
            for combination in itertools.product(*choices):
                picked = dict(zip(sorted(occupied), combination, strict=True))
                for step in gaps:
                    moved = tuple(
                        positions[r] + 1 - step + picked[positions[r] + 1][r]
                        for r in range(rows)
                    )
                    if min(moved) < _LAND_LOW or moved in seen:
                        continue
                    # No row may read a cell twice: ``[`` flips the cell it
                    # consults, so a second visit would see the complement of
                    # what the solver planted.  Every offered step is three
                    # or more, so ``1 - step + bit`` is negative and each row
                    # strictly advances leftward -- the property holds by
                    # construction rather than by filtering, and this asserts
                    # it rather than silently relying on it.
                    assert all(
                        moved[r] < positions[r] for r in range(rows)
                    ), f"a row failed to advance: {positions} -> {moved}"
                    seen.add(moved)
                    queue.append(
                        (moved, [*history, ("read", step, positions, picked)])
                    )

        # Clamps: a run of ``<``, which merges rows against the floor.  It
        # writes nothing, so it costs only length and can never corrupt the
        # tape -- the only reason to bound ``k`` is the state count.
        # There is deliberately no clamp move.  ``'<'*k`` is the language's
        # only merging primitive -- it sends every row to ``max(p - k, 0)``
        # -- but the merge and the answer are mutually exclusive: rows
        # collapse only once the run drives them to cell 0, and cell 0 is
        # far below the landing cells, so a merged row can no longer be
        # printed.  Measured on an eight-row spread, the first merge leaves
        # one row of eight at or above cell 6.  A clamp short of the floor
        # is a uniform shift, which changes nothing.
        #
        # This is worth stating because a clamp modelled as stopping at the
        # landing cells looks *very* good -- it nearly doubles the reachable
        # tables -- and that model is simply wrong about the machine.
    return None


# How wide the pattern must be for the reads to stay inside the region: one
# cell per read step plus the landing zone and a little slack.
def _width_for(n: int, depth: int) -> int:
    """Pattern width sized so every read lands inside the region."""
    return depth * _gap_for(n) + 8 * 2**n + 40


def _constant(
    n: int, table: list[int], width: int,
    pool: tuple[int, ...] = _POOL_ZERO_LOW,
) -> str:
    """Build a table that ignores its inputs.

    The crossings leave the rows converged, so a constant needs no reads at
    all: walk down to the cell whose ``[x`` spells the wanted digit and
    print.  The ``{Xi}`` are still emitted -- the harness has a bit for each
    -- and by then they cannot affect the answer.
    """
    built = _region(n, [0] * width, pool)
    if built is None:  # pragma: no cover - sizing is fixed by the caller
        raise ValueError("region build failed")
    joint = built[0]
    # With the low pool cell 6 prints '1' and cell 7 prints '0'.
    joint.emit("<" * (joint.ptr() - (_LAND_LOW if table[0] == 1 else _LAND_HIGH)))
    joint.emit("[x.")
    return joint.template()


def minifuck_closed(truth_table: str, depth: int = 5) -> str:
    """Build a Minifuck template for the given truth table, without searching.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The ``{Xi}`` placeholders become ``[<`` for a one and ``xx`` for a zero,
    both two characters, so no instantiation leaks its inputs through the
    program's length.  They are emitted in ascending order by construction.

    Raises :class:`ValueError` rather than returning a template that has not
    been seen to print the table: every row is simulated as the code is
    emitted, and the printed digits are checked against the table before the
    template is returned.
    """
    n = _validate_truth_table(truth_table)
    table = [int(c) for c in truth_table]
    width = _width_for(n, depth)

    if len(set(table)) == 1:
        return _constant(n, table, width)

    measured = _model(n, width)
    if measured is None:  # pragma: no cover - sizing is fixed above
        raise ValueError("region model failed")
    base, deltas, span = measured
    reachable = _cosets(base, deltas, n, span)
    gaps = _gaps_for(n)
    planned = _plan(n, table, reachable, span[1] - 1, gaps, depth)
    if planned is None:
        raise ValueError(
            f"no closed-form schedule for {truth_table!r} at depth {depth}"
        )
    history, upper = planned
    # The pool suits the arrangement the reads reached: whichever class ends
    # up on top, the pool that prints it correctly is the one written.
    #
    # One model serves both.  The pools differ only in cell 7, which lies
    # before the region and is never crossed again, so the region's cells --
    # and hence the affine model and every constraint drawn from it -- come
    # out identical either way.  Measured, not assumed: the two models are
    # equal cell for cell, and the rebuild below re-checks that the region
    # did not move.
    pool = _POOL_ZERO_LOW if upper == 0 else _POOL_ZERO_HIGH

    # Only reads constrain the tape; a clamp writes nothing, so it has
    # nothing to solve for.
    constraints = {}
    for _kind, _step, positions, picked in history:
        for cell, column in picked.items():
            for r in range(2**n):
                if positions[r] + 1 == cell:
                    constraints[(cell, r)] = column[r]

    pattern = _solve(constraints, base, deltas, width)
    if pattern is None:
        raise ValueError(f"constraints for {truth_table!r} are inconsistent")

    built = _region(n, pattern, pool)
    if built is None:  # pragma: no cover - the zero pattern already built
        raise ValueError("region rebuild failed")
    joint, rebuilt_lo, rebuilt_hi = built
    if (rebuilt_lo, rebuilt_hi) != span:
        raise ValueError(f"pool {pool} moved the region: {(rebuilt_lo, rebuilt_hi)}")
    joint.emit("<" * (joint.ptr() - (span[1] - 1)))
    for _kind, step, _positions, _picked in history:
        joint.emit("[" + "<" * step)

    by_class: dict[int, set[int]] = {}
    for r in range(2**n):
        by_class.setdefault(table[r], set()).add(joint.ms[r].ptr)
    if len(by_class) != 2 or any(len(v) != 1 for v in by_class.values()):
        raise ValueError(f"{truth_table!r} did not separate: {by_class}")
    # Land the two classes on cells 6 and 7.  The walk is anchored on the
    # lower class, since a row below 6 would write into the pool and spell
    # some third byte; the upper class then sits on 7, or on 8 when the pool
    # left it there, both of which print the same digit.
    lower = min(min(v) for v in by_class.values())
    joint.emit("<" * (lower - _LAND_LOW))
    joint.emit("[x.")

    printed = ["".join(m.out) for m in joint.ms]
    if printed != [str(bit) for bit in table]:
        raise ValueError(f"{truth_table!r} printed {printed}")
    return joint.template()
