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
read adds that function to the pointer.  Relative to each other a read moves
rows by 0 or -1, so rows **merge but never cross**.  Were the cells
*constant*, the reachable groupings would be exactly the contiguous blocks
of the row order, and only tables whose class sequence has at most two runs
would build -- 16 of 256 at three inputs.  Affine cells escape that, because
two rows sharing a position can still receive different bits.

A second consequence of affineness shapes the schedule: a non-constant
affine function on ``GF(2)^n`` is *balanced*, so a read taken while the rows
are still converged adds the same amount to every row.  Separation must come
first; only afterwards is each row alone on a cell, where that cell's free
bit steers it independently.

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
    """The per-read left step.  See :func:`_plan` for why it is this wide."""
    return 4 * 2**n + 2


def _plan(
    n: int, table: list[int], reachable: dict, start: int, gap: int, depth: int
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
    pool and spell some other byte, while a row above 7 is harmless.  The
    other orientation is therefore not merely unhandled -- swapping the two
    classes would need the walk to land the one class below the zero one,
    which the pool geometry does not allow.

    Returns ``(history, upper)`` where ``upper`` names the class that came
    out on top; the caller uses it to choose the pool.
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

        occupied: dict[int, list[int]] = {}
        for r in range(rows):
            occupied.setdefault(positions[r] + 1, []).append(r)
        if any(cell not in reachable for cell in occupied):
            continue
        choices = [sorted(reachable[cell]) for cell in sorted(occupied)]
        for combination in itertools.product(*choices):
            picked = dict(zip(sorted(occupied), combination, strict=True))
            moved = tuple(
                positions[r] + 1 - gap + picked[positions[r] + 1][r]
                for r in range(rows)
            )
            if min(moved) <= _LAND_HIGH + 1 or moved in seen:
                continue
            seen.add(moved)
            queue.append((moved, [*history, (positions, picked)]))
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
    gap = _gap_for(n)
    planned = _plan(n, table, reachable, span[1] - 1, gap, depth)
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

    constraints = {}
    for positions, picked in history:
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
    for _ in history:
        joint.emit("[" + "<" * gap)

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
