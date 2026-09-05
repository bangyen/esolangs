r"""Parameterized boolean generator for %^2^-1.

``%^2^-1`` has one accumulator and one control-flow command, ``t``, which
rewinds to the start of the program while the accumulator is nonzero.  There
is no forward jump and no skip, so a program that *reads* its inputs cannot
branch on them: ``docs/proofs.md`` records the proof that no such
program computes XOR or AND at any length, because ``n`` overwrites the
accumulator and nothing an earlier bit computed can survive the next read.

That theorem is a statement about the **reading** model.  It does not carry
over to embedded inputs, and this generator is the counterpart: the bits are
substituted into the program text, so no ``n`` ever runs and the erasure the
proof turns on never happens.

The construction needs no branch at all, which is what lets it fit a
language whose only jump target is position 0:

* ``l`` prints the accumulator **in decimal**, so an accumulator holding 0
  prints ``"0"`` and one holding 1 prints ``"1"``.  The answer therefore
  never has to be routed to a print site -- it only has to *be* the
  accumulator when the single ``l`` runs.
* Each input's setter is a short command string, and command strings compose
  as affine maps ``x -> a*x + b`` (``p`` gives ``a = -1``, ``'`` gives
  ``a = 0``, ``m`` doubles, ``s``/``i`` translate).  Chaining one map per
  input makes the final accumulator a *product-weighted* function of the
  bits -- genuinely nonlinear, because a later ``p`` negates everything the
  earlier bits contributed.  That nonlinearity is what reaches XOR, which no
  purely additive weighting separates: an additive one gives each row a
  distinct consecutive value and every affine-plus-threshold tail is
  monotone in it, so ``{00, 11}`` and ``{01, 10}`` can never be split.

**The solution is derived, not searched.**  Input 0 leaves one of two
constants in the accumulator; input 1 applies an affine map to it.  So for a
fixed value of input 1, the accumulator is affine in input 0, and the *slope*
is read straight off that column of the truth table: ``+1`` where the column
rises with input 0 and ``-1`` where it falls.  Choosing the two accumulator
values the answers land on then *forces* both offsets --
:func:`_offset_for` solves them, and a column whose two rows disagree about
the offset simply is not realisable that way.  :func:`_tail_for` prints,
translating the two class values onto ``1`` and ``0`` -- ``l`` prints the
accumulator in decimal, so no branch is needed and the over-3003 reset
never has to act as a comparator.

What remains enumerated is small and structural: the two constants input 0
contributes, whether it spells them with an explicit ``'`` erase, and the
pair of class values.  None of that is a search over *programs* -- the
multipliers come from the table and the offsets are solved -- so the emitted
program can be reasoned about rather than merely measured.

An earlier version enumerated setter assignments instead, a product of size
``len(options) ** (2 * n)`` guarded by a budget.  The derivation replaced it
outright and needs no budget.

Coverage: every table at ``n <= 2``, the sixteen two-input functions with XOR
and XNOR included; a one-input table is derived as the two-input table that
ignores its second input.

The derivation above does not generalise past two inputs -- it reads one
slope per column of a two-input table -- and the reason is structural: one
affine map per input composes into a *shared* value, which forces each
cofactor of the table to be constant or an affine image of one shared
function.  Only 88 of the 256 three-input tables satisfy that.

Above two inputs a second construction takes over, :func:`_cascade`, which
escapes that constraint by using the erase multiplier as a conditional -- the
position at which the accumulator is wiped depends on the inputs, which is a
branch realised arithmetically.  It builds every conjunction or disjunction
of literals at any arity, in ``2n + 4`` characters, which is why it is tried
first.

A third construction, :func:`_affine`, catches tables that are no subcube.
It composes one affine setter per input the way the two-input derivation
does, and like it the setters are **solved rather than searched**: after two
setters the accumulator is a vector of four values that the third maps by one
branch per value of the last input, so the table's even and odd rows are two
affine images of one shared vector.  Reading that backwards gives the whole
construction -- the vector's partition is forced by which rows the table
agrees on, two points fix each branch of the last setter, and the first two
setters invert by division.  An enumeration over branch pairs stood here
before, reaching the same 86 tables at 6.4 seconds for the arity against 0.8
and emitting longer programs; what is left of it is the equal-width spelling
by :func:`_spellings_by_width`, which is what lets an odd width gap close --
``_pad_pair`` pads with ``pp`` and refuses an odd shortfall, and parity-3's
witness wants branches of width 6 and 5.

A fourth construction, :func:`_ladder`, is the only one that computes *with*
the over-3003 reset instead of keeping clear of it.  Every path above is
affine in the accumulator -- each command acts uniformly on it, so the rows
keep their order and no two can be merged unless they already agree.  The
reset is the one primitive that is not affine: it maps everything above 3003
onto zero and leaves everything below alone, which is a threshold.  So the
ladder gives each input a weight, subtracts them into a negative accumulator
(negatives never reset, so stage one is exactly affine), and then lets the
reset read the weighted sum.  A threshold on a weighted sum is a majority,
which is why this path builds majority-3 -- the smallest OR of disjoint
subcubes, and one the composed-affine search cannot reach.

One bound is known about the ladder: a single reset is one threshold, and only
104 of the 256 three-input tables are linearly separable, so that shape cannot
be made total by widening its grid.  What lifts it is not more arithmetic but a
different *printing command*, which is the fifth construction,
:func:`_deep_band`.

Every path above prints with ``l``, which spells the accumulator in decimal and
so needs it to *be* 0 or 1 -- that is what pins the two answer classes to two
exact values.  ``e`` prints ``chr(acc & 0xFF)``, so a row only has to be
**congruent** to 48 or 49 mod 256, and with residues rather than values as the
target the reset can be used once per run of the table instead of once in total.
The band weights each input by a multiple of 256, so every row starts
congruent; sorting the rows by the weighted sum turns the table into runs; and
one stage clears each run, since the reset wipes only values past the limit.
Nothing is searched -- a wiped band thereafter takes the same translations as
the survivors, so the parking amount cancels out of their residue gap and each
stage's translation is fixed by a single congruence.

Two choices decide how far that reaches, and both are assumptions of the shape
rather than of the language.  Building the ladder **positive** makes every row
sum sit under the limit at once, so distinct sums need weights behaving like a
binary code -- at least ``2**n - 1`` units against the ``3003 // 256 == 11``
the limit allows, which stops at three inputs because four needs 15.  Building
it by **subtraction** instead puts the whole order below zero, where the reset
cannot fire and no budget applies.  And distinct sums are more than the table
needs: a cut *erases*, so every row it wipes lands on zero together whatever
the gaps between them were, and only the boundaries *between* runs need a full
residue system.  Rows may therefore collide when they share a class, which
prices a table's span by its number of runs instead of by ``2**n``, and admits
the popcount ladder -- every weight one -- on which parity spans ``n`` units
rather than ``2**n - 1``.

:func:`_deep_band` makes both of those choices, which is what carries it from
three inputs to four.  A positive-ladder version shipped alongside it for a
while and was removed once measured: it served no table the deep band does not
(0 of 256 at three inputs, where it was the only arity it reached) and its
programs were about four times longer (median 11492 characters against 3144),
so it was strictly dominated on both axes.

Four inputs are total on that path, all 65536 tables, against the 496 the
constructions above reach.  Parity has been executed on the interpreter through
six inputs.

What bounds :func:`_deep_band` is **distinctness**, and the count is worth
stating because the obvious guess is wrong: it is not the number of runs.  A
first reading had each run boundary consuming a residue system, which allows
about ``3003 // 256 == 11`` of them, but random five-input tables refuse at
five to eight runs, well inside that.

The real budget is the span distinctness costs.  Two rows sharing a value are
merged by the first cut that reaches them and can never be separated again, so
a weighting serves a table only if every collision it forces joins rows of one
class.  Keeping *all* rows distinct needs weights growing like a binary code, a
span of ``(2**n - 1) * 256``: 1792 at three inputs, which fits under the limit,
against 3840 at four and 7936 at five, which do not.  From four inputs on,
then, every weighting inside the limit collides some rows, and a table builds
only if its structure tolerates the collisions forced on it.

Four inputs are total because 3840 overshoots 3003 only slightly and enough
weightings survive.  At five the searched family collides two rows of opposite
classes in all 537792 of its weightings for a random table, which is why
generic five-input tables are refused by the deep band -- while *symmetric*
tables build at any arity, the popcount ladder spanning only ``n * 256`` and
colliding exactly the rows such a table already agrees on.  Parity-5,
majority-5 and threshold-5 all build, and parity is executed on the
interpreter through six inputs.

The distinctness budget is a property of reading the table off **one**
weighting, and :func:`_fold` is the construction that stops doing that.  It
treats the program as a sequence of *relocations*: rows start on a rigid
ladder, each use of the reset moves a group of rows by exactly ``3004`` plus
a slack bounded by the gap to its nearest survivor, the doubling ``m``
regrows gaps -- without it every wipe caps the spread at 3003, one short of
the jump, and the groups' cyclic order would be provably invariant -- and
rows of one class are merged by landing them on a shared value.  Once each
class is a single point, only their mutual gap carries a residue
requirement, and the final relocation's window spans a full residue system.
The plan is found by a search over the relative geometry, and the emitted
program is then mirrored on every row and asserted rather than trusted.

Five inputs close on that path: every table tried plans and executes -- all
256 at three inputs, 120 random at four, 300 random at five plus parity,
every threshold, near-parity and the fully alternating 32-run worst case,
and 40 at six inputs -- against the 496 the weighted constructions reach at
five.  The fold is not *proved* total at any arity it does not enumerate.

What bounds it is the **workspace**, and the bound is the ladder's footprint
rather than an arity check.  Rows start at ``-step * r``, so the ladder spans
``step * (2**n - 1)``, and the emitter lays it from a zero accumulator, which
means it has to fit inside ``[-3003, 0]``.  At the shipped spacing of 4 that
is 4092 at ten inputs, over the workspace, and no plan on such a ladder could
ever be emitted.  Halving the spacing halves the footprint to 2046, which is
what :data:`_FOLD_NARROW_STEP` is for.

But *uniform* spacing is itself the waste.  What the plan needs is only that
the rows sit at ``2**n`` **distinct** positions, and distinctness costs about
``2**n`` rather than the ``2 * (2**n - 1)`` a step-2 ladder spends.  The
packed ladder :data:`_FOLD_SUBSET_LADDER` meets the exact floor, ``2**n + 1``,
which is what carries **eleven inputs** at 2049 where the uniform one wanted
4094.

Twelve is where it ends, and there the wall is the move algebra rather than
the spelling.  The doubling ``m`` -- which this module proves is the only way
to reorder groups at all -- is offered only when the state's spread is at most
3002, and ``2**12`` distinct positions span at least 4095 wherever they sit.
So no twelve-input ladder ever doubles: the search from such a state
**exhausts after fifteen states**, an empty frontier rather than a budget.
Thirteen is impossible by counting alone, ``2**13`` positions against the 6007
values a ``p`` can address.  That bounds this construction, not the language:
as everywhere else here, what it misses is *unreached*, and the Lean wall in
``Esolangs.PctBooleanWall`` covers the reading model only.

Cost, since it decides where the fold sits in the chain: a fold build is
0.8ms at three inputs, 2.7ms at four, 89ms at five and 0.53s at six
(medians; worst observed 0.37s at five, 0.93s at six).  Two things make
that hold rather than degrade.  The beam runs down to eight points rather
than to the width at which the exhaustive search *starts* to struggle --
a target just under that width leaves states too wide to search and too
narrow to beam, and one 21-point table spent fifty seconds there and then
gave up, where beaming it to eight takes 0.37s.  And :func:`_deep_band` is
screened above four inputs instead of enumerated, because a refusal there
cost about eighteen seconds and a generic five-input table can never
build: only tables agreeing on every popcount class survive the collisions
its weightings force.  Screening moved a generic five-input build from
~18.3s to ~0.13s, at the price of the shorter programs the deep band would
have found for the asymmetric tables it happened to serve.

As before whatever it misses is *unreached*, not proved unreachable -- the
wall in ``docs/proofs.md`` covers the reading model only, and
nothing here bounds embedded-input programs in general.
``docs/limitations.md`` records what bounds are actually known.

Unlike the other parameterized generators, *which* command strings a setter
uses is derived per table rather than fixed by the language, so a bare
``{Xi}`` cannot be filled by a table-independent lambda.  The template
therefore carries a header naming each setter's two branches, followed by
the ``{Xi}`` placeholders themselves; :func:`fill` reads the header and
substitutes the branch each bit selects.  This mirrors ArrowQueue, whose
template likewise needs a structure-aware filler rather than a lambda.

Both branches of a setter come out the same width, so every instantiation of
a template has the same length and no program leaks its inputs through
``len()``.  The derivation and the cascade reach that by padding with ``pp``
-- two negations, which the interpreter executes and which compose to the
identity -- and :func:`_affine` by spelling both branches at a width they
share.  Padding can only close an even gap; respelling closes either.
"""

import re
from collections.abc import Iterator
from functools import cache
from itertools import pairwise, product

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["pct_squared_minus_one"]

#: The accumulator is zeroed when it exceeds this, checked before each command.
_LIMIT = 3003

#: Affine multipliers a setter may realise: identity, negate, erase, double.
_A_VALS = (1, -1, 0, 2)

#: Offsets considered for a setter branch.  The derived solutions never need a
#: magnitude past 8 (XOR's ``+/-8`` is the extreme), so this window is a
#: statement about the construction rather than a search budget.
_OFFSETS = range(-10, 11)

#: Accumulator values the answers ``(0, 1)`` may land on before the tail runs.
#: The tail has to move these onto ``0``/``1``, and :func:`_tail_for` does that
#: with one translation, which needs the pair a step apart -- so nearby pairs
#: are not merely the ones worth offering, they are the only ones that print.
_CLASS_PAIRS = tuple(
    (zero, one) for zero in range(-9, 10) for one in range(-9, 10) if zero != one
)

#: Separates the setter header from the program body in a template.
_HEADER_END = "\n"

#: Matches one setter declaration in the header, ``k=<zero>|<one>``.
_DECL_RE = re.compile(r"(\d+)=([^|;]*)\|([^;]*)")


def _sub_code(k: int) -> str | None:
    """Return code subtracting exactly ``k >= 0``, or ``None`` if impossible.

    ``s`` subtracts 2 and ``i`` subtracts 3, so every ``k`` is expressible as
    ``2a + 3b`` except ``k == 1``, which has no representation and is the one
    gap the callers route around.
    """
    if k == 0:
        return ""
    if k == 1:
        return None
    if k % 2 == 0:
        return "s" * (k // 2)
    return "i" + "s" * ((k - 3) // 2)


def _sub_with(k: int, threes: int) -> str | None:
    """Subtract ``k`` spending exactly ``threes`` ``i`` commands, or ``None``.

    :func:`_sub_code` always spells the shortest way, which fixes the width's
    parity; trading ``s`` for ``i`` is what lets a caller reach the other
    parity, since ``i`` moves 3 in one character where ``s`` needs two.
    """
    rest = k - 3 * threes
    if rest < 0 or rest % 2:
        return None
    return "i" * threes + "s" * (rest // 2)


def _affine_code(a: int, b: int) -> str | None:
    """Return a command string realising ``x -> a*x + b``, or ``None``.

    The offset is applied after the multiplier so it is not scaled by it.  A
    positive offset is spelled as a negated subtraction, ``-(-x - b)``.
    """
    head = {1: "", -1: "p", 0: "'", 2: "m"}.get(a)
    if head is None:
        return None
    if b == 0:
        tail: str | None = ""
    elif b < 0:
        tail = _sub_code(-b)
    else:
        inner = _sub_code(b)
        tail = None if inner is None else "p" + inner + "p"
    return None if tail is None else head + tail


def _apply(acc: int, code: str) -> int:
    """Run ``code`` on ``acc`` exactly as ``_Machine.step`` would.

    The over-3003 reset fires *before* each command, so it is applied inside
    the loop rather than once to the result.
    """
    for char in code:
        if acc > _LIMIT:
            acc = 0
        if char == "s":
            acc -= 2
        elif char == "i":
            acc -= 3
        elif char == "m":
            acc *= 2
        elif char == "p":
            acc = -acc
        elif char == "'":
            acc = 0
    return acc


def _pad_pair(zero: str | None, one: str | None) -> tuple[str, str] | None:
    """Pad two setter branches to equal width, preserving each one's value.

    Either branch may be ``None``, meaning the caller's arithmetic had no
    spelling in ``s``/``i``; that propagates as ``None`` rather than needing a
    guard at every call site.

    A program whose length depends on its inputs leaks them through
    ``len()``, so both branches of a setter must be the same width.  The pad
    is ``pp``: two negations, which the interpreter *executes* and which
    compose to the identity, so a later pass stripping characters the
    language merely ignores could not reintroduce the leak.  Only an even
    shortfall can be padded this way; an odd one returns ``None`` and the
    caller moves on to a different offset.
    """
    if zero is None or one is None:
        return None
    gap = len(one) - len(zero)
    if gap % 2:
        return None
    if gap > 0:
        return zero + "p" * gap, one
    return zero, one + "p" * (-gap)


@cache
def _tail_for(one_value: int, zero_value: int) -> str | None:
    """Return a tail printing ``1`` from ``one_value`` and ``0`` from ``zero_value``.

    ``l`` prints the accumulator in decimal and applies the over-3003 reset
    first, so the tail has to land the one-class on exactly 1 and the
    zero-class on 0 -- or above 3003, which the reset folds onto 0.

    One shape does it: a bare translation, moving both classes at once when
    they differ by one, optionally after a ``p`` so a reversed pair works
    too.  Two classes further apart than that have no tail at all.

    An amplify-then-clamp shape used to follow this one -- scale by
    ``2**j`` to drive the zero-class past the reset while the one-class is
    translated onto 1 -- and it never once fired.  It could not: every move
    it composed was a translation and ``m`` scales both classes alike, so
    such a body sends the class gap to ``2**j * (one - zero)``, negated by
    ``p``.  Landing on 1 and 0 needs a gap of exactly 1, which only
    ``j == 0`` gives, and that is the bare translation already tried above.
    Reaching the reset really would need a move that is not affine in the
    accumulator; the loop was scanning about two thousand bodies per call
    to rediscover the shape it started from.
    """
    for pre in ("", "p"):
        head_one = -one_value if pre else one_value
        head_zero = -zero_value if pre else zero_value
        if head_zero - head_one != -1:
            continue
        shift = head_one - 1
        code = _sub_code(shift) if shift >= 0 else _affine_code(1, -shift)
        if code is None:
            continue
        body = pre + code
        # The shift was solved from these very values, so the check confirms
        # rather than selects -- 236 candidate pairs over the reachable
        # range all pass it.  It stays because it is what makes the emitted
        # tail evidence rather than assertion.
        if (  # pragma: no branch - the arithmetic above cannot produce a miss
            _apply(one_value, body) == 1 and _apply(zero_value, body) == 0
        ):
            return body + "l"

    return None


def _column_slopes(rows: dict[tuple[int, int], int]) -> list[list[int]]:
    """Return the admissible slopes per column, read straight off the table.

    Holding input 1 fixed, the accumulator is affine in input 0, so that
    column of the table decides the multiplier input 1's setter must apply:
    ``+1`` where the column rises with input 0 and ``-1`` where it falls.
    This is the step that replaces a search -- the multipliers are read from
    the table, not tried.

    A column that does *not* depend on input 0 pins nothing, so every
    multiplier stays admissible for it.  Spelling then decides: ``0`` needs a
    leading ``'`` while ``1`` needs no character at all, and which is shorter
    depends on the rest of the program, so the choice is priced rather than
    guessed.  Listing the options here keeps that local to the derivation.
    """
    slopes = []
    for x1 in (0, 1):
        low, high = rows[(0, x1)], rows[(1, x1)]
        if low == high:
            slopes.append(list(_A_VALS))
        else:
            slopes.append([1 if high > low else -1])
    return slopes


def _offset_for(
    column: tuple[int, int],
    slope: int,
    values: tuple[int, int],
    classes: tuple[int, int],
) -> int | None:
    """Solve the offset a column needs, or ``None`` if it is inconsistent.

    For a fixed input 1, the accumulator is ``slope * v + offset`` where ``v``
    is what input 0 left behind.  Each row of the column therefore *forces*
    ``offset = target - slope * v``, and the column is realisable exactly when
    both its rows force the same value.  Nothing is searched here.
    """
    solved = None
    for x0 in (0, 1):
        target = classes[column[x0]]
        candidate = target - slope * values[x0]
        if solved is None:
            solved = candidate
        elif solved != candidate:
            return None
    return solved


def _solution(
    rows: dict[tuple[int, int], int],
    first: tuple[str, str],
    values: tuple[int, int],
    slopes: list[int],
    classes: tuple[int, int],
) -> tuple[list[tuple[str, str]], str] | None:
    """Assemble a full program from one candidate parameter set, or reject it.

    ``values`` is what input 0's two branches leave in the accumulator, and
    ``classes`` is the pair of accumulator values the answers 0 and 1 must
    land on.  Both offsets follow by :func:`_offset_for`; the candidate is
    rejected when either column cannot be made consistent.
    """
    offsets = []
    for x1 in (0, 1):
        column = (rows[(0, x1)], rows[(1, x1)])
        offset = _offset_for(column, slopes[x1], values, classes)
        if offset is None:
            return None
        offsets.append(offset)
    second = _pad_pair(
        _affine_code(slopes[0], offsets[0]), _affine_code(slopes[1], offsets[1])
    )
    if second is None:
        return None
    tail = _tail_for(classes[1], classes[0])
    if tail is None:
        return None
    return [first, second], tail


def _derive(truth_table: str) -> tuple[list[tuple[str, str]], str] | None:
    """Derive the shortest program for a two-input table.

    Input 0's setter leaves one of two constants in the accumulator, spelled
    either as a bare translation (the accumulator is already 0 at program
    start) or with an explicit ``'`` erase, which costs a character but frees
    the pair to be anything.  Both spellings are tried because neither
    dominates: the erase wins on constant tables, the bare form on XOR.

    The multipliers come from :func:`_column_slopes` -- read off the table,
    not searched -- and the offsets are then solved by :func:`_offset_for`,
    so what is enumerated here is only the constants input 0 contributes and
    the pair of class values.  Every candidate is priced and the shortest
    kept, so the result does not depend on enumeration order.
    """
    rows = {
        (x0, x1): int(truth_table[(x0 << 1) | x1]) for x0 in (0, 1) for x1 in (0, 1)
    }
    options = _column_slopes(rows)
    best: tuple[int, list[tuple[str, str]], str] | None = None
    for erase in (False, True):
        lead = 0 if erase else 1
        for zero_value in _OFFSETS:
            for one_value in _OFFSETS:
                first = _pad_pair(
                    _affine_code(lead, zero_value), _affine_code(lead, one_value)
                )
                if first is None:
                    continue
                for zero_slope in options[0]:
                    for one_slope in options[1]:
                        for classes in _CLASS_PAIRS:
                            found = _solution(
                                rows,
                                first,
                                (zero_value, one_value),
                                [zero_slope, one_slope],
                                classes,
                            )
                            if found is None:
                                continue
                            setters, tail = found
                            width = sum(len(z) for z, _ in setters) + len(tail)
                            if best is None or width < best[0]:
                                best = (width, setters, tail)
    if best is None:
        return None
    return best[1], best[2]


#: Setter branches for the arbitrary-arity minterm cascade.  Both are two
#: characters wide, so a setter leaks nothing through ``len()`` and the pad
#: parity problem never arises: a bare ``'`` erase is one character, and the
#: odd shortfall against an empty identity branch has no ``pp`` padding.
#: ``pp`` is two negations, which compose to the identity; ``'p`` zeroes and
#: then negates zero, which is still zero.
_CASCADE_IDENT = "pp"
_CASCADE_ERASE = "'p"

#: Loads 1 into the accumulator from 0: ``i`` subtracts 3, ``p`` negates to
#: 3, ``s`` subtracts 2.  The direct ``+1`` has no spelling -- ``_sub_code``
#: has no representation for 1 -- so the constant is built by this detour.
_CASCADE_ONE = "ips"


#: Negates a 0/1 accumulator: ``i`` subtracts 3, ``p`` negates, ``s``
#: subtracts 2, so ``r`` becomes ``1 - r``.  Appending it to a cascade turns
#: the indicator into its complement, which is what reaches ``OR``-``n`` and
#: ``NAND``-``n``.  It is the same three characters as :data:`_CASCADE_ONE`,
#: which builds 1 from an accumulator that is already 0.
_CASCADE_NOT = "ips"


def _subcube_of(truth_table: str, n: int) -> dict[int, int] | None:
    """Return the literals pinning ``truth_table``'s ON-set, or ``None``.

    The cascade computes a *conjunction of literals* -- a subcube.  Inputs the
    conjunction does not mention are free, so the ON-set is every row agreeing
    with the pinned inputs, and the table is realisable exactly when its ones
    are precisely that set.  A single minterm is the case where every input is
    pinned.

    The candidate pinning is read straight off the ON-rows: an input is pinned
    when every one-row agrees on it.  That is necessary but not sufficient, so
    the row count is checked against the subcube the pinning describes.
    """
    ones = [index for index, bit in enumerate(truth_table) if bit == "1"]
    if not ones:
        return None
    rows = [tuple((index >> (n - 1 - k)) & 1 for k in range(n)) for index in ones]
    fixed = {k: rows[0][k] for k in range(n) if len({row[k] for row in rows}) == 1}
    # A subcube on ``len(fixed)`` pinned inputs has exactly this many rows;
    # a table with the right pinning but the wrong count is not one.
    if len(ones) != 2 ** (n - len(fixed)):
        return None
    return fixed


def _cascade(truth_table: str, n: int) -> str | None:
    """Build a cascade template, or ``None`` if the table is not a subcube.

    The accumulator is loaded with 1 and then passed through one setter per
    input.  A pinned input's setter is the identity when its bit matches and
    an erase when it does not, so the accumulator survives as 1 exactly when
    every pinned bit matches; a free input's setter is the identity either
    way.  ``l`` then prints it in decimal, needing no branch -- the same
    printing route the two-input derivation uses.

    A table whose *complement* is a subcube is built by appending
    :data:`_CASCADE_NOT`, which maps the 0/1 indicator to ``1 - r``.  Together
    the two cases cover every conjunction and disjunction of literals at any
    arity: ``AND``-``n`` and single minterms directly, ``OR``-``n`` and
    ``NAND``-``n`` by complement.

    This is what lifts the two-input cap.  The derived path composes one
    affine map per input into a shared value, which forces each cofactor of
    the table to be constant or an affine image of one shared function; that
    constraint is what stops it at two inputs.  The cascade escapes it by
    using the erase multiplier as a conditional: the position at which the
    accumulator is wiped depends on the inputs, which is a genuine branch
    realised arithmetically in a language whose only jump target is 0.

    Tables that are neither a subcube nor the complement of one are not
    reachable this way, and are refused rather than served by a program
    computing the wrong function.  See ``docs/limitations.md`` for what is
    known about them.
    """
    fixed = _subcube_of(truth_table, n)
    complement = False
    if fixed is None:
        flipped = "".join("1" if bit == "0" else "0" for bit in truth_table)
        fixed = _subcube_of(flipped, n)
        complement = True
    if fixed is None:
        return None
    setters = []
    for k in range(n):
        if k not in fixed:
            setters.append((_CASCADE_IDENT, _CASCADE_IDENT))
        elif fixed[k]:
            setters.append((_CASCADE_ERASE, _CASCADE_IDENT))
        else:
            setters.append((_CASCADE_IDENT, _CASCADE_ERASE))
    header = ";".join(f"{k}={zero}|{one}" for k, (zero, one) in enumerate(setters))
    tail = (_CASCADE_NOT if complement else "") + "l"
    body = _CASCADE_ONE + "".join("{X" + str(k) + "}" for k in range(n)) + tail
    return header + _HEADER_END + body


#: Multipliers the wide search composes.  ``m`` doubles and ``p`` negates, so
#: ``mp`` is ``-2``, ``mm`` is ``4`` and ``mmp`` is ``-4``; widening past this
#: was measured and reaches no further table.
_WIDE_A_VALS = (0, 1, -1, 2, -2, 4, -4)

#: Offsets the wide search composes.  Measured: widening to ``+/-16`` reaches
#: no table that ``+/-12`` misses.
_WIDE_B_VALS = tuple(range(-12, 13))

#: Window a candidate spelling is checked against.  A spelling is admitted
#: because it *behaves* as ``a*x + b`` here, not because it matches a template,
#: which is what lets ``mp`` be found as ``a == -2`` without a rule for it.
_SPELL_WINDOW = range(-90, 91)

#: Longest command string the speller enumerates for one branch.
_SPELL_MAX = 7


@cache
def _spellings_by_width(a: int, b: int) -> dict[int, str]:
    """Map width to a command string realising ``x -> a*x + b`` at that width.

    :func:`_affine_code` gives one spelling per map, which fixes its width.
    That is what makes an odd width gap between a setter's two branches
    unfixable: :func:`_pad_pair` pads with ``pp`` and closes only even gaps.
    But a map usually has spellings of *several* lengths -- ``-6`` is ``sss``
    or ``ii`` -- so a pair whose natural widths differ by one can be respelled
    to a common width instead of padded.  Ninety-nine of the hundred maps in
    the grid have spellings of both parities, so this closes nearly every gap
    that padding refused.

    Candidates are admitted by behaviour on :data:`_SPELL_WINDOW` rather than
    by construction, so a spelling like ``mp`` is found for ``a == -2`` with no
    rule naming it.
    """
    out: dict[int, str] = {}
    frontier = [""]
    for _ in range(_SPELL_MAX + 1):
        for code in frontier:
            if len(code) not in out and all(
                _apply(v, code) == a * v + b for v in _SPELL_WINDOW
            ):
                out[len(code)] = code
        frontier = [c + ch for c in frontier if len(c) < _SPELL_MAX for ch in "simp'"]
    return out


#: One branch of a setter as an affine map, ``(a, b)`` for ``x -> a*x + b``.
_Branch = tuple[int, int]


#: Ladders the search runs, as ``(weights, base)``.  Every value is a multiple
#: of 250 and every rung stays within ``[-3003, 0]``, which is what keeps stage
#: one exactly affine: the reset fires only above 3003 and never on a negative
#: accumulator, so no rung clamps before the suffix asks it to.
#:
#: These eight are a *cover*, not a grid.  The full product of four weights and
#: four bases leaves 256 distinct ladders, of which 150 reach some table the
#: other paths miss; greedy set cover over their yields picks these eight, which
#: between them reach all twenty.  Searching the other 248 costs about fifty
#: seconds of build time and finds nothing further, so the cover is what ships.
_LADDERS = (
    ((250, 500, 250), 1000),
    ((500, 250, 250), 1000),
    ((250, 250, 250), 1000),
    ((250, 250, 500), 3000),
    ((500, 250, 500), 2750),
    ((1250, 250, 500), 2000),
    ((1250, 250, 1000), 2000),
    ((1250, 1250, 500), 2000),
)

#: Longest suffix the ladder search composes after stage 1.  The witnesses in
#: the shipped grid need at most ten characters; the search is breadth-first, so
#: this bounds the frontier rather than selecting among solutions.
_LADDER_DEPTH = 10


def _sub_of_width(k: int, width: int) -> str | None:
    """Spell a subtraction of exactly ``k`` in ``width`` characters, or ``None``.

    ``s`` subtracts 2 and ``i`` subtracts 3, so ``a`` esses and ``b`` eyes give
    ``2a + 3b == k`` in ``a + b == width`` characters; solving for the counts
    gives ``b == k - 2*width``.  Unlike :func:`_sub_code` this pins the width,
    which is what lets a setter's two branches be spelled to match.
    """
    eyes = k - 2 * width
    esses = width - eyes
    if eyes < 0 or esses < 0:
        return None
    return "i" * eyes + "s" * esses


def _even_width_for(k: int) -> int | None:
    """Narrowest *even* width at which ``k`` has a subtraction spelling.

    The hold branch of a ladder setter is ``pp`` repeated, which has only even
    widths, so the subtracting branch has to reach an even width to match it.
    """
    if k == 0:
        return 0
    width = -(-k // 3)
    if width % 2:
        width += 1
    while width <= k:
        if _sub_of_width(k, width) is not None:
            return width
        width += 2
    return None


def _ladder_setters(
    weights: tuple[int, ...], base: int
) -> tuple[list[tuple[str, str]], str] | None:
    """Spell a ladder's stage one, or ``None`` if some weight has no spelling.

    Each input's setter subtracts its weight when the bit is 1 and holds when it
    is 0.  The hold is ``pp`` repeated: two negations compose to the identity,
    and because every rung is negative the intermediate negation stays under the
    limit, so no reset fires inside a setter.  Both branches are spelled at one
    width, so no program leaks its inputs through ``len()``.
    """
    lead_width = _even_width_for(base)
    if lead_width is None:
        return None
    lead = _sub_of_width(base, lead_width) or ""
    setters = []
    for weight in weights:
        width = _even_width_for(weight)
        if width is None:
            return None
        code = _sub_of_width(weight, width)
        if code is None:  # pragma: no cover - _even_width_for just found one
            return None
        setters.append(("p" * width, code))
    return setters, lead


def _ladder_vector(
    setters: list[tuple[str, str]], lead: str, n: int
) -> tuple[int, ...]:
    """Return what stage one really leaves, run rather than solved.

    The arithmetic and the emitted characters have to agree, and modelling them
    separately is what let an earlier version claim a program the interpreter
    then contradicted: a hold negates, and a magnitude past the limit clamps to
    zero on the very next command.  Running :func:`_apply` over the code that is
    actually emitted removes that whole class of divergence.
    """
    out = []
    for index in range(2**n):
        code = lead
        for position, (zero, one) in enumerate(setters):
            code += one if (index >> (n - 1 - position)) & 1 else zero
        out.append(_apply(0, code))
    return tuple(out)


def _ladder_splits(vec: tuple[int, ...]) -> dict[str, str]:
    """Every two-class split of ``vec`` a suffix reaches, with its suffix.

    This is where the reset does the work the affine path cannot.  Stage one
    leaves the rows on an ordered ladder of negative values; a ``p`` turns the
    ladder positive, and then every row above 3003 folds onto zero while the
    rows below it survive.  That is a *threshold* on the weighted sum, evaluated
    by the one command the language spends no branch on -- and thresholds are
    exactly what an OR of disjoint subcubes needs.

    The printing tail is the ordinary one: the reset separates the classes in
    the body, and :func:`_tail_for` still lands them a step apart.  The wider
    amplify-then-clamp tail the docstring describes as never firing still never
    fires, and this path does not need it.
    """
    out: dict[str, str] = {}
    seen = {vec}
    frontier = [(vec, "")]
    while frontier:
        following = []
        for values, code in frontier:
            distinct = set(values)
            if len(distinct) == 2:
                low, high = sorted(distinct)
                for one_value, zero_value in ((low, high), (high, low)):
                    tail = _tail_for(one_value, zero_value)
                    if tail is None:
                        continue
                    table = "".join(
                        "1" if value == one_value else "0" for value in values
                    )
                    out.setdefault(table, code + tail)
            if len(code) >= _LADDER_DEPTH:
                continue
            for char in "simp'":
                nxt = tuple(_apply(value, char) for value in values)
                if nxt in seen:
                    continue
                seen.add(nxt)
                following.append((nxt, code + char))
        frontier = following
    return out


@cache
def _ladder_tables(n: int) -> dict[str, tuple[tuple[tuple[str, str], ...], str, str]]:
    """Every table the ladder path builds at ``n`` inputs.

    Derived for a whole arity in one pass and cached, the way
    :func:`_affine_tables` is: the suffix search is shared across every table a
    ladder reaches, so harvesting costs one sweep per parameter set rather than
    one per table.  Parameter sets that leave the same stage-one vector are
    searched once.
    """
    built: dict[str, tuple[tuple[tuple[str, str], ...], str, str]] = {}
    searched: set[tuple[int, ...]] = set()
    for weights, base in _LADDERS:
        if len(weights) != n:
            continue
        spelled = _ladder_setters(weights, base)
        if spelled is None:  # pragma: no cover - every shipped weight spells
            continue
        setters, lead = spelled
        vec = _ladder_vector(setters, lead, n)
        # Distinct parameters can leave the same rungs; the suffix search
        # depends only on those, so it runs once per vector.
        if vec in searched:
            continue
        searched.add(vec)
        for table, suffix in _ladder_splits(vec).items():
            if table not in built:
                built[table] = (tuple(setters), lead, suffix)
    return built


def _ladder(truth_table: str, n: int) -> str | None:
    """Build a ladder template, or ``None`` if the table is not one.

    This is the third construction above two inputs and the only one that uses
    the over-3003 reset as a computation rather than routing around it.  The
    other paths are affine in the accumulator: every command they compose acts
    uniformly on it, so the rows keep their order and no two of them can be
    merged except by agreeing already.  The reset is the one primitive that is
    *not* affine -- it maps everything above a threshold onto zero and leaves
    everything below it alone -- and a threshold on a weighted sum is precisely
    what a majority is.

    That is why this path reaches majority-3, which the composed-affine search
    does not: an OR of disjoint subcubes needs a running total to survive a
    gadget that erases, and the ladder keeps that total in the accumulator
    itself, letting the reset read it.

    The lead runs before any setter and is the same for every input
    combination, so it is emitted at the head of the body rather than as a
    setter of its own.
    """
    found = _ladder_tables(n).get(truth_table)
    if found is None:
        return None
    setters, lead, suffix = found
    header = ";".join(f"{k}={zero}|{one}" for k, (zero, one) in enumerate(setters))
    body = lead + "".join("{X" + str(k) + "}" for k in range(n)) + suffix
    return header + _HEADER_END + body


#: Byte values ``e`` prints as ``"0"`` and ``"1"``.  Unlike ``l``, which prints
#: the accumulator in decimal and so needs it to *be* 0 or 1, ``e`` prints
#: ``chr(acc & 0xFF)`` -- the accumulator only has to be *congruent* to these
#: mod 256, which is what lifts the ceiling every other path runs into.
_BYTE_ZERO = 48
_BYTE_ONE = 49

#: The band construction's weights are multiples of this, so every row starts
#: congruent mod 256 and the residue of a band is decided by one translation.
_BAND_UNIT = 256

#: Where a band construction parks its survivors after each wipe: positive, so
#: the next stage's translate can still push them over the limit, and far enough
#: under it that parking itself never clamps.
_BAND_PARK = 2000


#: How far the deep band's weights range, in whole residue systems.  Six is
#: where the measured coverage stops improving at four inputs; the search is
#: over weightings rather than programs, so this bounds a derivation's input,
#: not a program space.
_DEEP_CAP = 6

#: Where the deep band parks its survivors between cuts.  Positive and under
#: the limit, so a later cut's translation can still carry them across it.
_DEEP_PARK = 2000


def _deep_values(n: int, units: tuple[int, ...], mask: int) -> list[int]:
    """Row values for a weighting, with ``mask`` naming the complemented inputs.

    A weight applies when input ``k`` differs from its mask bit, so ``mask``
    relabels which corner of the cube carries the largest sum.  With
    nonnegative weights alone the all-ones row is always on top and the
    all-zeros row always at the bottom, which fixes most of the run structure
    a table can present; complementing an input is free -- the setter's two
    branches simply swap -- and it is what frees the order.
    """
    return [
        sum(
            u * _BAND_UNIT * (((r >> (n - 1 - k)) & 1) ^ ((mask >> k) & 1))
            for k, u in enumerate(units)
        )
        for r in range(2**n)
    ]


def _deep_plan(truth_table: str, n: int, values: list[int]) -> str | None:
    """Derive a deep band's body for one value vector, or ``None``.

    The ladder is built by *subtraction*, so every row sits at ``-sum``:
    negative, where the over-3003 reset cannot fire however large the weights
    are.  That is the whole escape from a positive ladder's unit budget, which
    exists only because building upward makes every row sum sit under the
    limit at once.

    Rows may share a value provided they share a class.  A cut erases -- every
    row it wipes lands on zero together, whatever the gaps between them were --
    so only the boundaries *between* runs need a full residue system, and the
    span a table costs is set by its number of runs rather than by ``2**n``.

    **None of the refusals below fire from the caller.**  The deep band tests
    each weighting for *legality* -- that every collision it causes joins rows
    of one class -- and a legal weighting has never been seen to fail to
    schedule.  That is what lets the search test legality instead of running
    this planner per candidate (commit 0921f249, which measured 63274 legal
    weightings inside the span budget with zero refusals), and the call site
    already carries a ``pragma: no cover`` saying so.  Re-measured here:
    n=3 exhaustive, 254 tables, 170592 legal weightings, 0 refusals; n=4
    sampled, 200 tables, 26016 legal, 0 refusals.

    So the ``continue``/``break``/``return None`` arms are the planner's own
    contract for a caller that has *not* screened its input, and they stay
    for that reason -- a planner that silently returned a body for an illegal
    weighting would emit a program computing the wrong function.
    """
    rows = range(2**n)
    groups: dict[int, set[str]] = {}
    for row in rows:
        groups.setdefault(values[row], set()).add(truth_table[row])
    # Two rows sharing a value can never be told apart again, so a collision
    # across classes would emit a program computing the wrong function.
    if any(len(classes) > 1 for classes in groups.values()):
        return None

    order = sorted(rows, key=lambda r: values[r], reverse=True)
    anchor = order[-1]
    live = _BYTE_ONE if truth_table[anchor] == "1" else _BYTE_ZERO

    for prefix in range(2**n):
        if prefix and len({truth_table[r] for r in order[:prefix]}) > 1:
            break  # pragma: no cover - screened by legality
        rest = order[prefix:]
        if not rest:
            break  # pragma: no cover - screened by legality
        if max(values[r] for r in rest) - min(values[r] for r in rest) > _LIMIT:
            continue  # pragma: no cover - screened by legality
        high = _LIMIT - max(values[r] for r in rest)
        low = (_LIMIT - min(values[r] for r in order[:prefix]) + 1) if prefix else 0
        low = max(low, 0)
        if low > high:
            continue  # pragma: no cover - screened by legality
        drop = next(
            (
                d
                for d in range(low, min(high, low + _BAND_UNIT) + 1)
                if _sub_code(d) is not None
            ),
            None,
        )
        if drop is None:
            continue  # pragma: no cover - screened by legality
        body = _deep_body(truth_table, n, values, order, anchor, live, prefix, drop)
        if body is not None:
            return body
    return None  # pragma: no cover - screened by legality


def _deep_body(
    truth_table: str,
    n: int,
    values: list[int],
    order: list[int],
    anchor: int,
    live: int,
    prefix: int,
    drop: int,
) -> str | None:
    """Spell one deep-band schedule, or ``None`` if a stage will not close."""
    rows = range(2**n)
    dropped = _sub_code(drop) if drop else ""
    if dropped is None:  # pragma: no cover - the caller chose a spellable drop
        return None
    # The ladder subtracted, so one ``p`` turns the order positive; the rows
    # the drop carried past the limit are wiped by the next command's reset.
    body = dropped + "p"
    current = {r: _apply(-values[r], dropped + "p") for r in rows}
    if {r for r in rows if current[r] > _LIMIT} != set(order[:prefix]):
        return None  # pragma: no cover - screened by legality
    cleared = set(order[:prefix])
    for row in cleared:
        # Empty from the screened caller: a legal weighting is planned at
        # ``prefix == 0`` -- measured over every table at two and three
        # inputs, 1332 bodies, all of them prefix 0 -- so nothing is carried
        # past the limit and there is nothing to clear.  The loop is the
        # planner's own handling of a prefix a wider caller could ask for.
        current[row] = 0  # pragma: no cover - screened by legality

    live_order = [r for r in order if r not in cleared]
    cuts = [
        i
        for i in range(1, len(live_order))
        if truth_table[live_order[i]] != truth_table[live_order[i - 1]]
    ]
    for cut in cuts:
        wipe = [live_order[i] for i in range(cut) if live_order[i] not in cleared]
        keep = [live_order[i] for i in range(cut, len(live_order))]
        if not wipe or len({truth_table[r] for r in wipe}) > 1:
            return None  # pragma: no cover - screened by legality
        low = _LIMIT - min(current[r] for r in wipe) + 1
        high = _LIMIT - max(current[r] for r in keep)
        if low > high or low <= 0:
            return None  # pragma: no cover - screened by legality
        band = _BYTE_ONE if truth_table[wipe[0]] == "1" else _BYTE_ZERO
        # A wiped band thereafter takes the same translations as the survivors,
        # so the parking cancels from their gap and one congruence fixes the
        # cut: the translation is solved, not searched.
        wanted = (live - band - current[anchor]) % _BAND_UNIT
        up = low + ((wanted - low) % _BAND_UNIT)
        if up > high:
            return None  # pragma: no cover - screened by legality
        raise_code = _affine_code(1, up)
        if raise_code is None:
            return None  # pragma: no cover - screened by legality
        raised = {r: _apply(v, raise_code + "s") for r, v in current.items()}
        down = _DEEP_PARK - max(raised.values())
        park = _affine_code(1, down)
        if park is None:
            return None  # pragma: no cover - screened by legality
        parked = {r: _apply(v, park) for r, v in raised.items()}
        if max(parked.values()) > _LIMIT:
            return None  # pragma: no cover - screened by legality
        body += raise_code + "s" + park
        current = parked
        cleared.update(wipe)

    base = (live - current[anchor]) % _BAND_UNIT
    # Nearest zero first: a shift is spelled one character per two units, so
    # taking the smallest keeps the program short.  An earlier version scanned
    # from -80 residue systems up and emitted the first that worked, which is a
    # ten-thousand-character run of ``s``.
    for shift in sorted((base + _BAND_UNIT * reps for reps in range(-8, 9)), key=abs):
        tail = _affine_code(1, shift)
        if tail is None:
            continue  # pragma: no cover - screened by legality
        printed = {r: _apply(v, tail) for r, v in current.items()}
        if all(
            (printed[r] & 0xFF) == (_BYTE_ONE if truth_table[r] == "1" else _BYTE_ZERO)
            for r in rows
        ):
            return body + tail + "e"
    return None  # pragma: no cover - screened by legality


def _deep_setters(
    units: tuple[int, ...], mask: int
) -> tuple[tuple[str, str], ...] | None:
    """Spell one setter per input, both branches at a common width."""
    setters = []
    for index, unit in enumerate(units):
        amount = unit * _BAND_UNIT
        if amount == 0:
            setters.append(("", ""))
            continue
        width = _even_width_for(amount)
        if width is None:  # pragma: no cover - every multiple of 256 spells
            return None
        code = _sub_of_width(amount, width)
        if code is None:  # pragma: no cover - the width just spelled it
            return None
        hold = "p" * width
        # The hold branch is ``pp`` repeated, two negations composing to the
        # identity, so both branches run the same number of commands and no
        # program leaks its inputs through ``len()``.
        setters.append((hold, code) if not (mask >> index) & 1 else (code, hold))
    return tuple(setters)


def _cross_class_diffs(truth_table: str, n: int) -> list[tuple[int, ...]]:
    """Difference vectors of the row pairs a weighting must keep apart.

    Two rows collide when their weighted sums tie, and a tie is a vanishing
    signed combination of the weights: writing ``d`` for the coordinatewise
    difference of the two rows' bits, the pair collides under ``units`` and
    ``mask`` exactly when ``sum(u_k * (-1)**mask_k * d_k) == 0``.  Only pairs
    of *different* class matter -- a collision inside a class is harmless,
    which is the whole reason the deep band reaches past the band -- and a
    vector and its negation forbid the same weightings, so each is kept once.
    Sixteen rows give 120 pairs but only about 32 distinct vectors, and the
    dedup is what makes the legality test cheap enough to replace planning.
    """
    seen: set[tuple[int, ...]] = set()
    for row in range(2**n):
        for other in range(row + 1, 2**n):
            if truth_table[row] == truth_table[other]:
                continue
            diff = tuple(
                ((row >> (n - 1 - k)) & 1) - ((other >> (n - 1 - k)) & 1)
                for k in range(n)
            )
            lead = next(x for x in diff if x)
            seen.add(diff if lead > 0 else tuple(-x for x in diff))
    return sorted(seen)


def _weighting_is_legal(
    units: tuple[int, ...], mask: int, diffs: list[tuple[int, ...]]
) -> bool:
    """Whether no cross-class pair collides under this weighting."""
    for diff in diffs:
        total = 0
        for k, unit in enumerate(units):
            total += -unit * diff[k] if (mask >> k) & 1 else unit * diff[k]
        if total == 0:
            return False
    return True


@cache
def _deep_weightings(n: int) -> tuple[tuple[int, ...], ...]:
    """Return the unit vectors worth trying, cheapest span first.

    Ordered by the span they cost, then flattest, which is the order the
    emitted program's length follows.  Vectors whose span exceeds the limit
    are dropped rather than tried: a weighting is measured in whole residue
    systems, so ``sum(units) * 256`` has to fit under 3003 and a sum past
    ``3003 // 256 == 11`` cannot schedule whatever the table looks like.
    That is not a heuristic -- every weighting observed to fail while its
    collisions were legal failed exactly here, at sum 12, span 3072.
    """
    return tuple(
        sorted(
            (
                units
                for units in product(range(_DEEP_CAP + 1), repeat=n)
                if any(units) and sum(units) <= _LIMIT // _BAND_UNIT
            ),
            key=lambda u: (sum(u), max(u), u),
        )
    )


def _deep_band(truth_table: str, n: int) -> str | None:
    """Build a deep-band template, or ``None`` if no weighting schedules it.

    This is the band shape with the two restrictions that bounded it removed.
    A positive ladder caps its weights at ``3003 // 256 == 11`` units, because
    every row sum has to sit under the limit at once; four inputs would need
    ``2**4 - 1 == 15`` and there is no weighting at all.  Here the ladder is
    negative -- nothing resets below zero -- so the unit budget does not
    exist, and rows are allowed to collide when they share a class, which
    prices a table's span by its number of runs instead of by ``2**n``.
    Parity rides the popcount ladder, every weight one, and so costs ``n``
    units rather than ``2**n - 1``.

    Weightings are tried in order of the span they cost -- which is the sum of
    the units, since each is a multiple of 256 -- so the emitted program is the
    shortest this construction builds rather than the first that schedules.
    What is *tested* per weighting is legality rather than schedulability:
    a collision is survivable exactly when it joins rows of one class, and a
    weighting whose collisions are all legal has never failed to schedule
    (63274 checked inside the span budget, none refused).  So the planner
    runs once, at the end, instead of once per candidate -- and the budget
    itself is derived rather than tuned, since every legal weighting observed
    to fail did so with ``sum(units) * 256`` past the limit.
    Ties go to the *flattest* weighting first, largest unit smallest: a table's
    span is set by its number of runs, and an even weighting is what collapses
    rows into runs.  Parity is the extreme case, built by the popcount ladder
    with every unit one, and ordering by ``max`` is what finds it immediately
    rather than after every degenerate weighting that ignores an input.

    Above four inputs the enumeration is **screened** rather than run.  Its
    own budget says why: keeping all rows distinct needs a span of
    ``(2**n - 1) * 256``, which is 3840 at four inputs -- close enough to
    the 3003 limit that enough weightings survive -- but 7936 at five, so
    every weighting there collides some rows and only a table whose
    structure tolerates the forced collisions builds.  In practice that
    means the symmetric tables, which the popcount ladder serves because
    its collisions are exactly the rows of equal popcount.  Measured: 0 of
    8 random five-input tables build, at about 18 seconds each to prove it,
    while parity-5 and majority-5 build in 0.14s.  Paying eighteen seconds
    for a refusal that a popcount check settles instantly is not worth the
    shorter program it occasionally finds, so the check runs first and the
    enumeration is skipped when it cannot pay off.
    """
    if n > 4 and any(
        len({truth_table[r] for r in range(2**n) if bin(r).count("1") == pop}) > 1
        for pop in range(n + 1)
    ):
        return None
    diffs = _cross_class_diffs(truth_table, n)
    for units in _deep_weightings(n):
        for mask in range(2**n):
            # Legality decides the weighting; the schedule then follows.  A
            # weighting whose collisions all join rows of one class has never
            # been observed to fail here -- 63274 legal weightings inside the
            # span budget were scheduled without one refusal -- so this test
            # replaces planning as the thing being searched for, and the plan
            # below runs once rather than once per candidate.
            if not _weighting_is_legal(units, mask, diffs):
                continue
            values = _deep_values(n, units, mask)
            body = _deep_plan(truth_table, n, values)
            if body is None:  # pragma: no cover - legality implies a schedule
                continue
            setters = _deep_setters(units, mask)
            if setters is None:  # pragma: no cover - a planned weighting spells
                continue
            header = ";".join(
                f"{k}={zero}|{one}" for k, (zero, one) in enumerate(setters)
            )
            placeholders = "".join("{X" + str(k) + "}" for k in range(n))
            return header + _HEADER_END + placeholders + body
    return None


_FOLD_STEP = 4

#: The ladder spacing tried when :data:`_FOLD_STEP` finds no plan.
#:
#: **What bounded the fold was the ladder's footprint, not the search.**  The
#: rows start at ``-step * r``, so the ladder spans ``step * (2**n - 1)``, and
#: the emitter has to lay it inside ``[-_LIMIT, 0]`` from a zero accumulator.
#: At the wide spacing that is 4092 against 3003 at ten inputs -- over the
#: workspace, so no such table could ever be emitted, however long the
#: planner searched.  (Before :func:`_fold_at` gated on the right bound, that
#: is exactly what happened: the descent wandered a relative-geometry space
#: the emitter would refuse, dead-ending 354 moves in with 420 of 514 points
#: unmerged.)  Halving the spacing halves the footprint to 2046, which fits,
#: and ten inputs then build and print every row on the interpreter.
#:
#: Two is the floor.  ``s`` subtracts 2 and ``i`` subtracts 3, so
#: :func:`_sub_code` spells every amount except 1 -- a step of 1 would need
#: the last input to subtract exactly 1 and has no spelling at any width.
#: With 2 the floor, ``2 * (2**n - 1) <= 3003`` caps *this* ladder at ten
#: inputs.  That is not where the fold ends, though: uniform spacing is
#: itself the waste, and :data:`_FOLD_SUBSET_LADDER` reaches eleven by
#: spending only what distinctness costs.
#:
#: It is a *fallback* rather than the default because the wider ladder is
#: what every shipped program is built on: at four inputs and below the
#: narrow ladder plans the same tables but emits different characters, so
#: trying it only on a miss keeps every template that builds today
#: byte-identical and confines the change to the arities that refused.
_FOLD_NARROW_STEP = 2

#: The packed ladder: ``(2, 3, 4, 8, 16, ..., 2**(n-2) * 2)``.
#:
#: **A uniform ladder wastes half the workspace.**  The fold needs the rows
#: to sit at ``2**n`` *distinct* positions -- two rows sharing a value are
#: merged by the first cut reaching them and can never be separated again --
#: but a uniform ladder buys that distinctness by spending ``step * (2**n -
#: 1)``, which is far more than distinctness costs.  What it actually costs
#: is a set of weights whose ``2**n`` subset sums are distinct, and the
#: cheapest such set spans about ``2**n`` rather than ``2 * 2**n``.
#:
#: The floor is easy to state.  The sums are ``2**n`` distinct non-negative
#: integers, so the largest is at least ``2**n - 1``; the minimum weight is 2
#: (``2a + 3b`` cannot spell 1), so no subset sums to 1, and by symmetry none
#: sums to ``S - 1``.  Two values inside ``[0, S]`` are therefore unattainable
#: and ``S >= 2**n + 1``.  The set above **meets that floor exactly**: 2 and 3
#: cover the small residues that a pure doubling ladder cannot reach without
#: a weight of 1, and the powers above them behave like a binary code, so all
#: ``2**n`` sums are distinct with a total of exactly ``2**n + 1``.
#:
#: That is what lifts the arity.  The narrow uniform ladder spends 4094 at
#: eleven inputs against the 3003 the workspace allows; this one spends
#: **2049**, and eleven inputs build and execute.  Twelve needs 4097, which
#: does not fit, so this shape ends there -- and no ladder of any shape
#: reaches thirteen, since ``2**13 + 1`` exceeds even the two-sided ``6007``
#: positions a ``p``-negated ladder could address.
#:
#: **Row order stops matching position order here**, which is the one thing
#: the rest of the fold had assumed.  On a uniform ladder row ``r`` sits at
#: ``-step * r``, so consecutive rows are adjacent points and a table's runs
#: are contiguous; with these weights row 1 (weight 1024) sits *below* row 8
#: (weight 16).  :func:`_fold_at` therefore groups runs over rows sorted by
#: position rather than over ``range(2**n)``.  Everything downstream -- the
#: plan search, the moves, the emitter -- already worked in positions and
#: needed no change.
#: The value is the ladder's irregular *head*, the two weights that are not
#: powers; :func:`_fold_subset_weights` appends the doubling tail to it.
#: They are what meets the floor -- a pure doubling ladder from 2 spans
#: ``2 * (2**n - 1)``, and it is 2 and 3 together that cover the small sums a
#: weight of 1 would otherwise be needed for.
_FOLD_SUBSET_LADDER = (2, 3)

#: One point of a fold plan: ``(top, span, cls, rows)`` -- the group's highest
#: row value relative to the state's top, how far its rows extend below it
#: (0 once it has been wiped and its rows merged), its class, and the rows.
_FoldPoint = tuple[int, int, str, frozenset[int]]
_FoldState = tuple[_FoldPoint, ...]

#: One move: ``(kind, k, c, victims)`` -- ``"m"`` doubles, ``"d"``/``"u"``
#: wipe the bottom/top ``k`` groups with relocation amount ``c``.
_FoldOp = tuple[str, int, int, frozenset[int]]

#: The largest bridge state :func:`_fold_to_cofactors` will search.  Measured,
#: not chosen: exhaustively over ``n <= 4`` the 33628 tables that build never
#: hand the bridge more than eight points, and the adversaries built to grow
#: the state (a function of the first ``k`` inputs embedded at ``n = 8, 10,
#: 12``) top out at four.  Above this the search is what makes a doomed arity
#: expensive -- a 512-point state burns the 50000-state cap for 192s -- while
#: contributing no build, so it is declined instead of paid for.
_COFACTOR_BRIDGE_POINTS = 8

#: A point in the emitter's mirror: a raw row or a merged set of rows.
_FoldKey = int | frozenset[int]


def _fold_norm(items: list[_FoldPoint]) -> _FoldState:
    """Sort by top descending and rebase so the highest top is 0."""
    ordered = sorted(items, key=lambda t: (-t[0], t[1]))
    top = ordered[0][0]
    return tuple((p - top, s, c, i) for p, s, c, i in ordered)


def _fold_merge(items: list[_FoldPoint]) -> _FoldState | None:
    """Coalesce equal positions, or ``None`` on a cross-class collision.

    Two points at one value are indistinguishable forever after, so a
    collision is a merge -- legal only within a class, and only between
    already-wiped points (a group with extent has rows at *several* values,
    so an "equal top" is not an equal anything).
    """
    by_pos: dict[int, list[tuple[int, str, frozenset[int]]]] = {}
    for p, s, c, i in items:
        by_pos.setdefault(p, []).append((s, c, i))
    out: list[_FoldPoint] = []
    for p, grp in by_pos.items():
        if len(grp) == 1:
            s, c, i = grp[0]
            out.append((p, s, c, i))
        else:
            if len({c for _, c, _ in grp}) != 1:
                return None
            if any(s != 0 for s, _, _ in grp):
                return None
            out.append((p, 0, grp[0][1], frozenset(x for _, _, i in grp for x in i)))
    return _fold_norm(out)


def _fold_moves(
    state: _FoldState, kcap: int | None = None
) -> "Iterator[tuple[str, int, int, frozenset[int], _FoldState]]":
    """Yield every candidate move from ``state``.

    The algebra is relative: a wipe relocates its victims by exactly
    ``3004 + slack`` (the reset line is at 3003 and a landing is at 0), so a
    dive of the bottom ``k`` groups maps each survivor ``q_i`` above the
    victims to ``q_i - c`` for any ``c`` in ``[3004, 3003 + q_1]`` -- the
    window is the gap to the nearest survivor's *bottom*, and every choice
    of absolute placement realises every ``c`` in it.  Rises mirror.  The
    doubling ``m`` scales every gap and is what lets a gap outgrow 3004,
    without which a landing can never split two survivors (each wipe caps
    the spread at 3003, so the cyclic order of the groups would be invariant
    and any table whose runs alternate four or more times would be out of
    reach -- an exhaustive search over wipe-only plans finds exactly that).
    """
    m = len(state)
    kmax = m if (kcap is None or m <= 8) else min(m, kcap)
    top_all = max(p for p, _, _, _ in state)
    bot_all = min(p - s for p, s, _, _ in state)
    spread = top_all - bot_all
    # Doubling needs the whole state inside [-3003, 3003] afterwards, and an
    # odd spread of 3003 has no integer placement, hence the -2.
    if 0 < spread * 2 <= 2 * _LIMIT - 2:
        yield (
            "m",
            0,
            0,
            frozenset(),
            _fold_norm([(p * 2, s * 2, c, i) for p, s, c, i in state]),
        )
    if len({c for _, _, c, _ in state}) == 1 and any(s or p for p, s, _, _ in state):
        allids = frozenset(x for _, _, _, i in state for x in i)
        yield ("d", m, _LIMIT + 1, allids, ((0, 0, state[0][2], allids),))
    asc = sorted(state, key=lambda t: t[0])
    for k in range(1, min(m, kmax + 1) if m > 8 else m):
        vic = asc[:k]
        if len({c for _, _, c, _ in vic}) != 1:
            continue
        vcls = vic[0][2]
        vt = vic[-1][0]
        surv = asc[k:]
        q1 = min(p - s for p, s, _, _ in surv) - vt
        if q1 < 1:
            continue
        cmin, cmax = _LIMIT + 1, _LIMIT + q1
        cands = {cmin, cmax}
        qtops = [(p - vt, s, c) for p, s, c, _ in surv]
        for qt, qspan, qcls in qtops:
            if qspan == 0 and qcls == vcls and cmin <= qt <= cmax:
                cands.add(qt)
            for adj in (qt - 4, qt - 2, qt + 2, qt + 4):
                if cmin <= adj <= cmax:
                    cands.add(adj)
        for (qa, _, _), (qb, _, _) in pairwise(qtops):
            mid = (qa + qb) // 2
            if cmin <= mid <= cmax:
                cands.add(mid)
        for amount in cands:
            items = [(p - vt - amount, s, cc, ii) for p, s, cc, ii in surv]
            items.append((0, 0, vcls, frozenset(x for _, _, _, i in vic for x in i)))
            hi = max(p for p, _, _, _ in items)
            lo = min(p - s for p, s, _, _ in items)
            if hi - lo > 2 * _LIMIT:
                continue
            merged = _fold_merge(items)
            if merged is not None:
                yield (
                    "d",
                    k,
                    amount,
                    frozenset(x for _, _, _, i in vic for x in i),
                    merged,
                )
    desc = sorted(state, key=lambda t: -t[0])
    for k in range(1, min(m, kmax + 1) if m > 8 else m):
        vic = desc[:k]
        if len({c for _, _, c, _ in vic}) != 1:
            continue
        vcls = vic[0][2]
        vb = min(p - s for p, s, _, _ in vic)
        surv = desc[k:]
        q1 = vb - max(p for p, _, _, _ in surv)
        if q1 < 1:
            continue
        cmin, cmax = _LIMIT + 1, _LIMIT + q1
        cands = {cmin, cmax}
        qtops = [(vb - p, s, c) for p, s, c, _ in surv]
        for qt, qspan, qcls in qtops:
            if qspan == 0 and qcls == vcls and cmin <= qt <= cmax:
                cands.add(qt)
            for adj in (qt - 4, qt - 2, qt + 2, qt + 4):
                if cmin <= adj <= cmax:
                    cands.add(adj)
        for (qa, _, _), (qb, _, _) in pairwise(qtops):
            mid = (qa + qb) // 2
            if cmin <= mid <= cmax:
                cands.add(mid)
        for amount in cands:
            items = [(amount - (vb - p), s, cc, ii) for p, s, cc, ii in surv]
            items.append((0, 0, vcls, frozenset(x for _, _, _, i in vic for x in i)))
            hi = max(p for p, _, _, _ in items)
            lo = min(p - s for p, s, _, _ in items)
            if hi - lo > 2 * _LIMIT:
                continue
            merged = _fold_merge(items)
            if merged is not None:
                yield (
                    "u",
                    k,
                    amount,
                    frozenset(x for _, _, _, i in vic for x in i),
                    merged,
                )


def _fold_done(state: _FoldState) -> bool:
    """Two wiped points at most: one value per class, nothing unmerged."""
    return len(state) <= 2 and all(t[1] == 0 for t in state)


def _fold_sig(state: _FoldState) -> tuple[tuple[int, int, str], ...]:
    return tuple((p, s, c) for p, s, c, _ in state)


def _fold_search(
    state: _FoldState, maxdepth: int = 40, cap: int = 5_000
) -> list[_FoldOp] | None:
    """Best-first search to a two-point state, or ``None``.

    States are keyed by their relative geometry -- ids do not matter for
    reachability -- and ranked by point count first, so contractions are
    pursued before excursions.

    **The cap is what makes a miss returnable.**  It was 2_000_000, and at
    that size it did not do a cap's job: states are expanded at about 3700 a
    second, so exhausting it took roughly nine minutes per call and a wide
    table refused only after tens of minutes -- which is the failure this
    module elsewhere refuses to ship, since a caller can handle a raise and
    cannot handle a build that does not return.

    5_000 is measured rather than tuned, against the arities that carry a
    claim.  Every table at ``n <= 5`` builds exactly as it did at the old
    value -- all 256 at three inputs and 40-table samples at four and five,
    the same *sets* either way, every row re-executed on the interpreter at
    one fill width -- while a six-input sample builds 8 of 8 with a slowest
    build of 1.6s.

    **The refusal that used to motivate the cap is now a gate.**  This
    docstring recorded the cap as buying an eight-input refusal in about 13
    seconds where the old value took over nine minutes.  Both numbers are
    stale: eight inputs *build*, in about 0.3s, and what refuses is an arity
    past ten, which :func:`_fold_at` rejects on the ladder's footprint before
    any search runs.  The cap is therefore doing far less than it was
    credited with -- no measured table reaches it -- and it stays as a
    latency guard on a state the descent leaves short rather than as the
    thing that bounds acceptance.
    """
    import heapq

    start = _fold_norm(list(state))
    if _fold_done(start):
        return []
    seen = {_fold_sig(start)}
    ctr = 0
    heap: list[tuple[int, int, int, _FoldState, list[_FoldOp]]] = [
        (len(start), 0, 0, start, [])
    ]
    while heap:
        if len(seen) > cap:
            return None
        _, depth, _, st, ops = heapq.heappop(heap)
        if depth >= maxdepth:
            continue
        for kind, k, c_, vids, nb in _fold_moves(st, kcap=3):
            sg = _fold_sig(nb)
            if sg in seen:
                continue
            nops = [*ops, (kind, k, c_, vids)]
            if _fold_done(nb):
                return nops
            seen.add(sg)
            ctr += 1
            heapq.heappush(heap, (len(nb), depth + 1, ctr, nb, nops))
    return None


def _fold_beam(
    state: _FoldState,
    target: int = 2,
    width: int = 1,
    maxsteps: int | None = None,
) -> list[_FoldOp] | None:
    """Reduce a state down to ``target`` points, or ``None``.

    **A deterministic descent, not a beam.**  ``width`` defaults to 1: take
    the best-ranked move each step and never reconsider.  The name and the
    parameter survive so the old breadth can be re-measured, not because
    anything asks for it.

    ``target`` defaults to 2, which is the whole reduction -- the plan no
    longer stops at a remainder for :func:`_fold_search` to close.  Two
    measurements license that, both recorded on
    :data:`_FOLD_DESCENT_TARGET`: the rank ties this breaks arbitrarily are
    confluent, and descending the whole way builds everything the old split
    built while reaching an arity it refused.

    ``maxsteps`` defaults to ``None``, meaning the budget is *derived from
    the state* -- ``_FOLD_STEP_SLOPE * points + _FOLD_STEP_SLACK``, where
    the starting points are the table's runs.  The budget is what used to
    bind, and binding it to a flat number capped the arity by accident: see
    :data:`_FOLD_STEP_SLOPE`.  Pass an integer to override.
    """
    start = _fold_norm(list(state))
    if len(start) <= target:
        return []
    if maxsteps is None:
        maxsteps = _FOLD_STEP_SLOPE * len(start) + _FOLD_STEP_SLACK
    beam: list[tuple[_FoldState, list[_FoldOp]]] = [(start, [])]
    seen = {_fold_sig(start)}
    for _ in range(maxsteps):
        nxt: list[tuple[_FoldState, list[_FoldOp]]] = []
        for st, ops in beam:
            for kind, k, c_, vids, nb in _fold_moves(st, kcap=3):
                sg = _fold_sig(nb)
                if sg in seen:
                    continue
                seen.add(sg)
                nops = [*ops, (kind, k, c_, vids)]
                if len(nb) <= target:
                    return nops
                nxt.append((nb, nops))
        if not nxt:
            return None
        nxt.sort(key=lambda t: (len(t[0]), len(t[1])))
        beam = nxt[:width]
    return None


def _fold_apply(state: _FoldState, op: _FoldOp) -> _FoldState | None:
    kind, k, c_, vids = op
    for kk, k2, cc, vv, nb in _fold_moves(state, kcap=None):
        if (kk, k2, cc, vv) == (kind, k, c_, vids):
            return nb
    return None


#: **The beam's breadth was the target's fault, and this removes it.**
#:
#: Width 1 is not a beam at all -- it takes the single best-ranked move each
#: step and never reconsiders, which is a deterministic rule.  At the old
#: target of 8 that very nearly worked (76 of 80 six-input tables), and the
#: four exceptions looked like a property of those tables.  They are not.
#: Varying the target while measuring the width each exception needs shows
#: the requirement moving with the *target*, not with the table:
#:
#:     table        tgt4  tgt6  tgt8  tgt10  tgt12
#:     w8-loser        9     9     9      2      1
#:     needs9-a        9     9     9      1      1
#:     needs9-b        9     9     9      9      9
#:
#: Two of the three stop needing breadth entirely once the beam is allowed to
#: stop at 10 rather than 8.  The reduction is forced; asking it to land on
#: exactly 8 points is what was not.
#:
#: **And the underlying cause is the step budget, not the target.**  Tracing
#: the greedy reduction on the exceptions shows it never reaching a dead end:
#: it is still descending when ``maxsteps`` expires, one or two moves short --
#: `needs9-b` stands at 9 points on the last permitted step.  Many steps make
#: no progress (runs of ``19 -> 19``, ``13 -> 13 -> 13``) because the best
#: available move does not always reduce the count, and the final points are
#: the slowest.  So the "width 9" the exceptions appeared to need was not a
#: property of those tables at all: raising ``maxsteps`` from 90 to 150
#: builds **all five** of them at target 8 and width 1.  Both knobs work
#: because both buy the same thing -- a target of 12 is reached sooner, and a
#: budget of 150 lets 8 be reached at all.  The target is what ships because
#: it costs nothing per table that already builds, where a larger budget is
#: paid on every refusal.
#:
#: So the target moves to 12 and the width to 1.  Measured against the old
#: ``target=8, width=48`` over 416 tables -- all 256 at three inputs,
#: 60-table samples at four and five, 40 at six -- the built set is
#: **identical**, nothing lost and nothing gained, every row re-executed on
#: the interpreter at one fill width, and the sweep runs in 56.8s against
#: 131.5s.  At seven inputs, which carries no claim, the two disagree on one
#: table each way.
#:
#: The target is not free to grow: at 16 the *five*-input tables start
#: refusing (28 of 30), since a wide remainder hands ``_fold_search`` more
#: than it can close.  10, 12 and 14 all give full greedy acceptance; 12 is
#: the middle of that band.
#:
#: **The ties do not matter, and the search is not needed.**  The reduction
#: meets steps where 5 to 12 candidate moves tie at the best rank and it
#: takes an arbitrary one, which looked like the one place a rule was still
#: missing.  It is not: breaking those ties at *random* -- a fresh
#: permutation before every ranking, so no two runs agree -- builds 20 of 20
#: six-input tables under every seed tried, at three seeds by four budgets.
#: (At the old ``maxsteps`` of 90 the same test built 5 to 11, which is the
#: budget artefact again and not the ties.)  Arrival order therefore buys
#: step-efficiency, not correctness, and the reduction is confluent.
#:
#: Given that, the descent has no reason to stop early and hand a remainder
#: to :func:`_fold_search`.  Running it to two points instead builds every
#: table the old split built -- 424 tables at three through seven inputs,
#: none lost -- and *gains* five at seven inputs, with every row executed on
#: the interpreter.  It also reaches an arity the split refused outright:
#: two random eight-input tables build in about four seconds each and print
#: all 256 rows, where the shipped configuration raises.
#:
#: So the fold's plan is now a single deterministic descent.  The programs
#: are byte-identical at three and four inputs and differ above that (the
#: descent finds its own ending rather than the search's), which is why this
#: is a behaviour change rather than a refactor.
_FOLD_DESCENT_TARGET = 2

#: The descent's step budget, as ``slope * points + slack`` rather than a
#: flat number.  **The starting point count is the run count** -- the fold
#: opens with one point per run of the sorted table, so a budget written
#: against points is written against the table's own structure.
#:
#: **The descent terminates without it.**  The budget is a latency guard,
#: not the reason the loop stops, and the argument is structural rather than
#: measured:
#:
#: * *The point count never rises.*  ``_fold_merge`` only ever coalesces
#:   equal positions, and every branch of :func:`_fold_moves` passes its
#:   items through it -- the doubling ``m`` and the full-collapse ``d`` map
#:   ``p`` points to ``p`` and 1 respectively.  So ``p`` is non-increasing
#:   along any trajectory, and at most ``points - target`` steps can ever be
#:   productive.
#: * *Every state stays in the workspace.*  Both relocation branches guard
#:   with ``if hi - lo > 2 * _LIMIT: continue``, and the doubling is offered
#:   only when ``spread * 2 <= 2 * _LIMIT - 2``.  Positions therefore live in
#:   a window of ``2 * _LIMIT + 1`` values, so the signatures available at a
#:   fixed ``p`` are finitely many.
#: * *Revisits are forbidden.*  The descent adds every generated successor to
#:   ``seen`` and skips anything already there.
#:
#: A non-increasing measure, finitely many states per value of that measure,
#: and no revisits: the loop must either reduce ``p`` or run out of
#: successors, and running out is the ``if not cands`` refusal.  Checked as
#: well as argued -- over 53110 successor states sampled at four through six
#: inputs, none raised the point count and none left the workspace.
#:
#: So the slope only has to be generous enough not to cut a descent short,
#: and **four inputs is enumerated rather than sampled**: folding all 65534
#: non-constant four-input tables gives a worst of 78 steps at 16 points,
#: against the 144 this budget allows there -- 1.8x headroom over an
#: exhaustive population, not a lucky sample.  The whole ``pts -> steps``
#: table is regular: the maximum climbs smoothly with the point count and
#: the worst ratio peaks at **5.25** around 12 points, then falls away.
#:
#: Sampling at wider arities agrees (worst 5.65 at five inputs, at 17
#: points) and, importantly, does *not* converge downward -- the worst
#: observed ratio rose with every widening, 4.25 through 5.65.  That is why
#: the slope is not presented as derived: it is a bound chosen to sit well
#: above an observed peak that small states, not large ones, produce.  What
#: makes that acceptable is the termination argument above -- the budget
#: does not decide what builds, only how long a doomed descent runs -- plus
#: the fold being the last route tried, so a loose budget costs refusal
#: latency and nothing on a table that builds.
#:
#: **What the cost actually depends on is the run-length word**, and that is
#: exhaustive rather than sampled: writing each table as its sequence of run
#: lengths, every one of the 127 distinct words at three inputs and all
#: 32767 at four map to a *single* step count, with no exceptions.  Since
#: 65534 tables share those 32767 words in pairs -- a table and its
#: complement -- the cost is complement-invariant too, and nothing about the
#: table beyond the word matters.
#:
#: The dependence is on the word as a *sequence*, not as a multiset: only 27
#: of the 2248 rotation-and-reflection classes at four inputs are
#: cost-invariant.  Position is what moves it.  Holding the point count,
#: run count and class sizes fixed and sliding one length-2 run through an
#: otherwise alternating word takes the cost from 27 steps to 78 -- the same
#: table shape, three times the work, decided by where the defect sits.  The
#: worst tables in the whole four-input enumeration are exactly that: near
#: alternating with a single late defect.
#:
#: **All of the above is about the greedy descent's path length, which is
#: not an invariant of anything.**  It is one policy's walk, tie-broken by
#: the order :func:`_fold_moves` yields and carrying a ``seen`` set that
#: makes each step depend on the whole history, so it is not even a graph
#: distance.  Comparing it against one -- a breadth-first search over
#: signatures with a global visited set -- it is *optimal on 4 of 196*
#: three-input words, and can be 14 steps where 6 suffice.  Some words the
#: descent takes 9 steps on are 2 steps from done.
#:
#: Against the true distance the structure is completely different.  Within
#: a fixed run count the optimal cost takes exactly **two adjacent values**
#: (spread 1, against the greedy spread of 9), and it does *not* depend on
#: the exact run lengths at all -- only on which runs exceed 1, with zero
#: ambiguity at every run count.  So the incompressibility this docstring
#: used to record is a fact about the heuristic, not about the fold: the
#: exact lengths that "matter without limit" matter only to greedy's walk.
#:
#: **The optimal cost has a closed form.**  Writing ``r`` for the run count
#: and calling a slot *long* when its run exceeds 1::
#:
#:     cost(word) = 2 * r - 3 - (r % 2) + [every middle slot is long]
#:
#: where the *middle* slots are ``{(r - 1) // 2, r // 2}`` -- one slot for
#: odd ``r``, two for even.  The first three terms are ``base(r)``, the
#: minimum cost at that run count: 1, 2, 5, 6, 9, 10, 13 at ``r = 2..8``.
#: The bracket is the ``delta``, which is 0 or 1, so the two-adjacent-values
#: spread above is exactly this term.
#:
#: **Definitions, because the quantity is what the prior investigation got
#: wrong.**  ``cost`` is the breadth-first distance from the start state --
#: one point per run, at ``-_FOLD_STEP * first_row`` with span
#: ``_FOLD_STEP * (len - 1)`` -- to a :func:`_fold_done` state, over
#: :func:`_fold_sig` signatures with a *global* visited set, generating
#: successors with :func:`_fold_moves` at ``kcap=None``.  ``kcap`` does not
#: bind below nine points (``kmax = m if m <= 8``), so this is the shipped
#: move set for every word measured; at ``r >= 9`` the descent's ``kcap=3``
#: is a different graph and is not covered by this rule.
#:
#: The harness's start state is the same object :func:`_fold` builds, and
#: that is checked rather than assumed: over all 65534 non-constant
#: four-input tables, the state constructed from the run-length word alone
#: has the identical :func:`_fold_sig` to the one built from the table, 65534
#: of 65534.  Those tables carry only 32767 distinct words -- a table and its
#: complement share one -- which is where the cost's complement-invariance
#: comes from.
#:
#: Measured over **1091 words with zero mismatches**: exhaustive at three
#: inputs for ``r <= 6`` (all 119 words) plus two of the seven ``r == 7``
#: words, the ones with the defect at either end; exhaustive
#: over ``>1``-patterns at four and five inputs for ``r <= 5``, each pattern
#: carried by several words that vary *where* the mass sits (the axis that
#: killed the earlier candidates), 322 and 468 words; 300 uniformly random
#: words at five and six inputs; and an adversarial round on the shapes the
#: rule is most likely to get wrong -- pairs differing only at a middle slot,
#: extreme mass contrasts, the same pattern at 8, 16, 32 and 64 rows.
#:
#: The delta is pinned at the run counts where its shape changes.  At
#: ``r == 6`` the middle is a *pair* of slots and the conjunction is what
#: matters: at four inputs ``(1, 1, 2, 1, 1, 10)`` and ``(1, 1, 1, 2, 1, 10)``
#: each cost 9 with one middle slot long, while ``(1, 1, 2, 2, 1, 9)`` costs
#: 10 with both.  At ``r == 7`` the middle is the single slot 3, and
#: ``(1, 1, 1, 2, 1, 1, 25)`` costs exactly 11 -- depths 9 and 10 exhaust
#: with no solution and depth 11 finds a plan (393s) -- so the ``+1`` is
#: present at a run count no other measurement reached.  It is measured
#: against ``base(7) == 10``, which is itself proved twice: a full BFS on
#: ``(2, 1, 1, 1, 1, 1, 1)`` and on ``(1, 1, 1, 1, 1, 1, 2)`` at three inputs
#: (1.17M states, 344s and 195s), and an iterative deepening on
#: ``(1, 1, 1, 1, 1, 1, 26)`` at five that finds nothing at depth 9 and a
#: plan at depth 10.
#:
#: **The delta's mechanism, re-derived.**  A one-move finish from three
#: points requires an untouched span-0 point, and *only a wipe zeroes a
#: span*: the wipe collapses its victims to ``(0, 0, cls, ids)`` while every
#: survivor keeps its span, and :func:`_fold_merge` refuses to coalesce
#: anything whose span is nonzero.  Since every wipe takes ``asc[:k]`` or
#: ``desc[:k]`` -- 8116 of 8116 moves checked contiguous, none interior -- a
#: long *middle* run is the one group no prefix or suffix reaches without
#: dragging a neighbour, so it costs the extra move.  Verified as a
#: necessary condition on all 1005 reachable three-point states, with 462 of
#: them admitting a one-move finish as a positive control.
#:
#: The earlier telling of this mechanism was wrong in one detail worth
#: keeping straight: a ``k >= 2`` wipe does *not* require span-0 victims
#: (414 of 840 partial sweeps observed have a spanned victim).  The span-0
#: requirement lives in the landing, not the sweep.
#:
#: The ``base(r)`` half is regularity rather than proof.  Censusing optimal
#: plans gives ``r - 1 + 2 * floor((r - 2) / 2)`` moves, split as
#: ``floor((r - 2) / 2)`` doublings and the rest wipes -- ``(1, 15)`` is one
#: ``d``; ``(1, 1, 14)`` is ``d`` then ``u``; ``(1, 1, 1, 13)`` is
#: ``d, m, d, u, u``; ``(1, 1, 1, 1, 1, 11)`` is four ``d``, two ``m``,
#: three ``u``.  A doubling is what lets a landing split two survivors, so
#: the count tracks how often the cyclic order must be broken.  That is a
#: mechanism sketch, not a lower-bound argument: the closed form is
#: validated by measurement, and the ``m``-count is observed rather than
#: derived.
#:
#: **Four recorded counterexamples were greedy artifacts, and the record is
#: corrected here.**  Every pair below was measured against the descent's
#: path length, not against a distance, and under BFS each pair *agrees*:
#: ``(19, 2, 11)`` and ``(23, 2, 7)`` both cost 3; ``(34, 20, 10)`` and
#: ``(10, 20, 34)`` both cost 3; ``(40, 4, 8, 12)`` and ``(12, 4, 8, 40)``
#: both cost 6.  So the cums-mod-4-with-cap key and the ``min(x, K)``
#: recodings were never falsified against the true cost -- and the middle
#: -slot rule's supposed death at four inputs was the same mistake:
#: ``(1, 14, 1)`` costs 3 where ``(1, 1, 14)`` costs 2, exactly as the rule
#: says, against the claim that all 3-run words there cost 2 alike.  The
#: recorded ``base`` table was wrong too: ``base(2) = 1`` at every arity, not
#: 0 at four inputs -- a two-run word always has a run longer than 1, so its
#: start state has a nonzero span and cannot already be done.
#:
#: What this does *not* say: the ``>1``-pattern is sufficient only where it
#: was measured (``r <= 5`` at four and five inputs, ``r <= 6`` at three),
#: and ``r >= 8`` is untested at every arity -- ``base(8) = 13`` is the
#: closed form's prediction, not a measurement.  A full BFS at seven runs
#: costs about six minutes and 1.2M states, so the ladder above that is a
#: compute question rather than an open one.
#:
#: One law was found and refuted: ``3 * points`` bounds the exhaustive
#: three-input maxima exactly, with the bound attained.  It does not survive
#: -- four inputs violate it at ten points and five inputs reach 5.65 -- so
#: the tight small-arity fit is a coincidence of small states rather than
#: the shape of the algorithm.
#:
#: One thing measured and *rejected*: widening ``kcap`` from 3 to 6 in the
#: descent's move generation.  A re-implemented harness suggested it removed
#: long plateaus, but that harness started from ``2**n`` points where the
#: real descent starts from the run count, so it was not this algorithm.
#: Instrumenting the shipped beam gives byte-identical ratios at both values
#: -- median 1.92, worst 5.10 either way -- so the widening buys nothing.
#:
#: Substituting it for the flat 400 is a **no-op where 400 was enough**: over
#: 387 tables at three through eight inputs the emitted programs are
#: byte-identical, every one re-executed on the interpreter.  Where 400 was
#: *not* enough it lifts an arity, which is the point -- eight inputs already
#: used 359 steps, so nine overran the flat budget and built 1 of 3 random
#: tables, where the derived bound builds 3 of 3 and prints all 512 rows.
#:
#: What it is not any more is *arity-capping* by accident.
#: **Plan length is not program length, and for size it is close to the
#: wrong objective.**  Ops have wildly different prices: within one plan a
#: dive at 3004 costs 1490 characters from a resting accumulator and 4 when
#: the accumulator is already near, a doubling costs 751, and the finish
#: over a thousand.  The charge is the arithmetic distance travelled,
#: spelled in unary -- :func:`_sub_code` is ``k // 2`` characters -- so op
#: count barely correlates with emitted length.  Cutting a plan from 17 ops
#: to 6 was measured to save 13% of characters; optimising characters
#: directly saves 60% and more.
#:
#: **The cost model is closed form**, verified to zero error on all 56
#: constructible three-input tables.  Each op is priced by mirroring the
#: emitter's position updates, and :meth:`_FoldEmitter.finish` solves a
#: single congruence -- ``need = (-(byte(hi) - byte(lo)) - pos[lo]) % 256``,
#: whose unique in-window solution ``u`` costs ``u // 2 + 31``.  A candidate
#: plan can therefore be priced without emitting it.
#:
#: That model explains a fact worth recording: character cost is **not**
#: complement-invariant, though plan length is.  The answer bytes are 48 and
#: 49, so which class lands on top flips a ``+-1`` and moves the congruence
#: by 2 mod 256 -- about 127 characters.  ``01100111`` costs 5424 where its
#: complement ``10011000`` costs 5306.
#:
#: **One construction ships nothing yet but is verified:** every three-run
#: table builds from three greedy rises, no search -- 3176 to 3185
#: characters against this generator's 9838 to 10640, within 1 to 8 of the
#: enumerated optimum, each program executed on the interpreter with every
#: row correct at one fill width.  The cost is nearly independent of the run
#: lengths and of the arity.
#:
#: Three attempts to generalise that failed, recorded so they are not
#: retried.  Reranking this descent by characters instead of point count
#: looked like a 27.7% win and is **272% worse** on tables all variants
#: build -- the apparent saving was selection bias from abandoning hard
#: tables, at 116/254 coverage against 206/254.  A fixed catalogue of the
#: observed optimal shapes, walked greedily, saturates at 34 of 40 however
#: wide the amount branching.  And greedy on the exact cost model builds 8
#: of 40 at a mean of **-67%**.  Exact edge weights are not enough without a
#: cost-to-go term; the choice of move is not greedily determined.
_FOLD_STEP_SLOPE = 8
_FOLD_STEP_SLACK = 16


#: The plan for a table, read off its run-length word rather than searched.
#:
#: **What the descent was rediscovering.**  The optimal plan does not depend
#: on the run lengths, only on which runs are longer than 1.  Writing that as
#: the word's ``>1``-pattern, every word sharing a pattern admits the same
#: plan: mining every optimal plan (breadth-first to the minimum depth, then
#: enumerating all plans at that depth) and replaying the symbolic form onto
#: other words with the same pattern builds 40 of 40 targets for every
#: pattern at ``r <= 4``, including 16- and 32-row targets from 8-row
#: sources.
#:
#: **The amounts come from four symbols**, which is what makes a plan
#: replayable at all: ``cmin`` is the minimum relocation, ``cmax`` relocates
#: by the whole gap to the nearest survivor, ``land j`` lands exactly on
#: survivor ``j`` -- necessarily same-class and already wiped, which is the
#: merge -- and the doubling carries no amount.  The vocabulary is pinned
#: rather than assumed: a breadth-first search restricted to ``cmin``,
#: ``cmax`` and the doubling reaches 250 of the 254 non-constant three-input
#: tables, and the four it misses are exactly the alternating and
#: near-alternating words, which need a landing.
#:
#: **The key is ``(r, delta, pat[1])``** -- the run count, the middle-slot
#: predicate that :data:`_FOLD_STEP_SLOPE` already records as setting the
#: *cost*, and the second slot.  Over all 59 patterns mined at ``r <= 5``
#: that key is unambiguous: 12 groups, no two patterns in a group
#: disagreeing.  ``pat[1]`` discriminates only at ``r == 4`` -- both its
#: values give identical plans at ``r == 5``, which is why the table below
#: carries duplicate rows there -- so it is sufficient rather than
#: necessary.
#:
#: Every entry is the same three-phase program: *peel* the ends inward with
#: alternating ``d1``/``u2`` wipes at ``cmax``, *park* with one wipe at
#: ``cmin`` and then double, and *close* with a wipe onto a landing followed
#: by ``cmax`` wipes ending at ``k == 2``.  ``delta`` adds one peel step,
#: which is the ``+1`` of the cost form.  The first move's direction follows
#: which side carries the long run: dive when it sits low, rise when high.
#:
#: Coverage is the table's extent and nothing else.  At three inputs the
#: construction builds 196 of the 254 non-constant tables and the 58 misses
#: are all ``r >= 6``; at four inputs it builds **3880 of 3880** tables with
#: ``r <= 5`` and none above.
#:
#: **Plan length improves everywhere; characters improve in aggregate but
#: not per table.**  The plan is 4.89 ops against the descent's 12.21 (max 7
#: against 19), and that is uniform.  Characters are 34.9% fewer over the
#: whole three-input arity, but the two are not the same axis -- as
#: :data:`_FOLD_STEP_SLOPE` records, op count barely correlates with emitted
#: length -- and of the 196 tables the construction serves, **20 emit longer
#: than the descent would**, the worst ``10010011`` at 11453 characters
#: against 8483.  Shortening those is a separate problem from planning them,
#: and the three attempts recorded on :data:`_FOLD_STEP_SLOPE` say it is not
#: a greedy one.
#:
#: Every claim above is checked by execution rather than replay: all 254
#: three-input tables and 100 four-input tables on the constructed path emit
#: through the public generator and print every row correctly on the
#: interpreter.  ``r >= 6`` is not tabulated, so those tables fall through
#: to the descent below, which is unchanged.
_FOLD_SKELETONS: dict[tuple[int, int, int], tuple[tuple[str, int, str], ...]] = {
    (2, 0, 0): (("u", 1, "cmax"),),
    (2, 0, 1): (("d", 1, "cmax"),),
    (2, 1, 1): (("d", 1, "cmax"), ("d", 1, "cmax")),
    (3, 0, 0): (("d", 1, "cmax"), ("u", 2, "cmax")),
    (3, 1, 1): (("d", 1, "cmax"), ("d", 1, "cmax"), ("d", 2, "cmax")),
    (4, 0, 0): (
        ("d", 1, "cmin"),
        ("m", 0, "m"),
        ("d", 1, "cmax"),
        ("u", 1, "land2"),
        ("u", 2, "cmax"),
    ),
    (4, 0, 1): (
        ("u", 1, "cmin"),
        ("m", 0, "m"),
        ("d", 1, "land1"),
        ("d", 1, "cmax"),
        ("u", 2, "cmax"),
    ),
    (4, 1, 1): (
        ("d", 1, "cmax"),
        ("d", 1, "cmin"),
        ("m", 0, "m"),
        ("d", 1, "cmax"),
        ("d", 1, "land2"),
        ("d", 2, "cmax"),
    ),
    (5, 0, 0): (
        ("d", 1, "cmax"),
        ("u", 2, "cmin"),
        ("m", 0, "m"),
        ("d", 1, "land1"),
        ("d", 1, "cmax"),
        ("u", 2, "cmax"),
    ),
    (5, 0, 1): (
        ("d", 1, "cmax"),
        ("u", 2, "cmin"),
        ("m", 0, "m"),
        ("d", 1, "land1"),
        ("d", 1, "cmax"),
        ("u", 2, "cmax"),
    ),
    (5, 1, 0): (
        ("d", 1, "cmax"),
        ("u", 2, "cmax"),
        ("u", 1, "cmin"),
        ("m", 0, "m"),
        ("u", 1, "cmax"),
        ("u", 1, "land2"),
        ("u", 2, "cmax"),
    ),
    (5, 1, 1): (
        ("d", 1, "cmax"),
        ("u", 2, "cmax"),
        ("u", 1, "cmin"),
        ("m", 0, "m"),
        ("u", 1, "cmax"),
        ("u", 1, "land2"),
        ("u", 2, "cmax"),
    ),
}


def _fold_geometry(
    state: _FoldState, kind: str, k: int
) -> tuple[int, int, list[tuple[int, int, str]], str] | None:
    """Return ``(cmin, cmax, survivor tops, victim class)`` for a wipe.

    Mirrors the window :func:`_fold_moves` computes, so a symbolic amount can
    be resolved against a state without enumerating that state's moves.
    """
    if kind == "d":
        asc = sorted(state, key=lambda t: t[0])
        vic, surv = asc[:k], asc[k:]
        if not surv:
            return None
        vt = vic[-1][0]
        q1 = min(p - s for p, s, _, _ in surv) - vt
        tops = [(p - vt, s, c) for p, s, c, _ in surv]
    else:
        desc = sorted(state, key=lambda t: -t[0])
        vic, surv = desc[:k], desc[k:]
        if not surv:
            return None
        vb = min(p - s for p, s, _, _ in vic)
        q1 = vb - max(p for p, _, _, _ in surv)
        tops = [(vb - p, s, c) for p, s, c, _ in surv]
    return _LIMIT + 1, _LIMIT + q1, tops, vic[0][2]


def _fold_resolve(
    state: _FoldState, kind: str, k: int, sym: str
) -> tuple[_FoldOp, _FoldState] | None:
    """Turn one symbolic step into a concrete move on ``state``.

    A landing is the semantic content of a step -- it is the merge -- so it
    is matched first, by the survivor index the symbol names; the index is
    what transfers between words of one pattern.  ``cmax`` and ``cmin`` fall
    back in that order.
    """
    want: int | None = None
    if sym != "m":
        geo = _fold_geometry(state, kind, k)
        if geo is None:
            return None
        cmin, cmax, tops, vcls = geo
        if sym.startswith("land"):
            j = int(sym[4:])
            if j >= len(tops):
                return None
            qt, qspan, qcls = tops[j]
            if qspan != 0 or qcls != vcls or not cmin <= qt <= cmax:
                return None
            want = qt
        else:
            want = cmax if sym == "cmax" else cmin
    for kk, k2, c, vids, nb in _fold_moves(state, kcap=None):
        if kk != kind or k2 != k:
            continue
        if sym == "m" or c == want:
            return (kk, k2, c, vids), nb
    return None


def _fold_construct(state: _FoldState) -> list[_FoldOp] | None:
    """Emit a plan from the state's run-length word, or ``None``.

    No enumeration, no beam and no backtracking: the plan is read from
    :data:`_FOLD_SKELETONS` and each amount is solved against the live
    state, so the work is one geometry computation per op.  Returns ``None``
    when the pattern is not tabulated or a step does not resolve, and the
    caller falls through to the descent.
    """
    st = _fold_norm(list(state))
    if _fold_done(st):
        return []
    word = tuple(len(ids) for _p, _s, _c, ids in sorted(st, key=lambda t: -t[0]))
    pat = tuple(1 if x > 1 else 0 for x in word)
    r = len(pat)
    mids = {(r - 1) // 2, r // 2}
    delta = 1 if all(pat[i] for i in mids) else 0
    skel = _FOLD_SKELETONS.get((r, delta, pat[1] if r > 1 else 0))
    if skel is None:
        return None
    ops: list[_FoldOp] = []
    for kind, k, sym in skel:
        got = _fold_resolve(st, kind, k, sym)
        if got is None:
            return None
        op, st = got
        ops.append(op)
    return ops if _fold_done(st) else None


def _fold_plan(state: _FoldState) -> list[_FoldOp] | None:
    """Plan a full reduction, or ``None`` if the search gives up.

    The plan is *constructed* where the table's run-length word is one
    :data:`_FOLD_SKELETONS` tabulates -- every word of at most five runs --
    and only otherwise searched.  A rotation pre-pass then wipes every
    unwiped group once (a bottom wipe at the minimum relocation lands above
    everything and preserves the cyclic order), because a group with extent
    cannot be a collision target and the search stalls while any remain.
    """
    built = _fold_construct(state)
    if built is not None:
        return built
    st = _fold_norm(list(state))
    pre: list[_FoldOp] = []
    guard = 0
    # (see _FOLD_BEAM_WIDTHS for why the beam is tried narrow first)
    while any(s > 0 for _, s, _, _ in st) and len(st) > 1:
        guard += 1
        # A latency guard, not a bound the pre-pass needs: each pass wipes
        # one group and a wipe clears that group's extent, so the loop is
        # already linear in the groups carrying any.  20000 random states
        # at two through eight groups peaked at 0.69 of this allowance and
        # none reached it; the same structural argument recorded on
        # :data:`_FOLD_STEP_SLOPE` for the descent applies here.
        if guard > 2 * len(state) + 4:  # pragma: no cover - never reached
            break
        hit = None
        for kk, k2, cc, vv, nb in _fold_moves(st, kcap=1):
            if kk == "d" and k2 == 1 and cc == _LIMIT + 1:
                hit = ((kk, k2, cc, vv), nb)
                break
        if hit is None:
            break
        pre.append(hit[0])
        st = hit[1]
    # Descend all the way, not to a remainder the search then closes: see
    # :data:`_FOLD_DESCENT_TARGET`.
    wide = _fold_beam(st, target=_FOLD_DESCENT_TARGET, width=1)
    if wide is None:
        wide = []
    cur: _FoldState | None = st
    for op in wide:
        assert cur is not None  # nosec B101
        cur = _fold_apply(cur, op)
        if cur is None:  # pragma: no cover - replays a move the beam made
            return None
    assert cur is not None  # nosec B101
    # Normally a no-op: the descent already reached two points, and
    # :func:`_fold_search` returns ``[]`` for a finished state.  It stays as
    # the fallback for a state the descent leaves short.
    rest = _fold_search(cur)
    if rest is None:
        return None
    return pre + wide + rest


class _FoldEmitter:
    """Exact mirror of every row's accumulator, emitting body characters.

    Each method both appends the characters and applies their effect to all
    rows, asserting after every step that the interpreter would agree --
    which points get wiped, that nothing leaves the workspace, and finally
    that every row's value is congruent to its answer byte.
    """

    def __init__(
        self, truth_table: str, n: int, weights: tuple[int, ...] | None = None
    ) -> None:
        self.table = truth_table
        self.rows = 2**n
        if weights is None:
            weights = _fold_uniform(n, _FOLD_STEP)
        start = _fold_positions(n, weights)
        self.pos: dict[_FoldKey, int] = {r: start[r] for r in range(self.rows)}
        self.cls: dict[_FoldKey, str] = {r: truth_table[r] for r in range(self.rows)}
        self.body: list[str] = []

    def _sub(self, k: int) -> str:
        code = _sub_code(k)
        assert code is not None, k  # nosec B101
        return code

    def descend(self, k: int) -> None:
        if k == 0:
            return
        if k == 1:
            self.descend(3)
            self.plain_rise(2)
            return
        assert k >= 2  # nosec B101
        assert all(v <= _LIMIT for v in self.pos.values())  # nosec B101
        self.body.append(self._sub(k))
        for p in self.pos:
            self.pos[p] -= k

    def plain_rise(self, k: int) -> None:
        if k == 0:
            return
        if k == 1:
            self.plain_rise(3)
            self.descend(2)
            return
        assert k >= 2  # nosec B101
        assert all(-_LIMIT <= v <= _LIMIT for v in self.pos.values())  # nosec B101
        assert all(v + k <= _LIMIT for v in self.pos.values())  # nosec B101
        self.body.append("p" + self._sub(k) + "p")
        for p in self.pos:
            self.pos[p] += k

    def preshift(self, delta: int) -> None:
        if delta < 0:
            self.descend(-delta)
        elif delta > 0:
            self.plain_rise(delta)

    def double(self, *, next_is_rise: bool) -> None:
        top = max(self.pos.values())
        bot = min(self.pos.values())
        spread = top - bot
        assert 2 * spread <= 2 * _LIMIT  # nosec B101
        want_top = 1501
        if next_is_rise:
            # The next command sequence opens with ``p``, which wipes
            # anything below -3003, so the doubled state must fit both ways.
            want_top = max(spread - 1501, 0)
            assert want_top <= 1501, spread  # nosec B101
        self.preshift(want_top - top)
        assert all(2 * v <= _LIMIT for v in self.pos.values())  # nosec B101
        self.body.append("m")
        for p in self.pos:
            self.pos[p] *= 2

    def _vic(self, vids: frozenset[int]) -> set[_FoldKey]:
        vic: set[_FoldKey] = {
            p for p in self.pos if (set(p) if isinstance(p, frozenset) else {p}) <= vids
        }
        got: set[int] = set()
        for p in vic:
            got |= set(p) if isinstance(p, frozenset) else {p}
        assert vic, vids  # nosec B101
        assert got == vids, vids  # nosec B101
        return vic

    def dive(self, c: int, vids: frozenset[int]) -> None:
        vic = self._vic(vids)
        assert len({self.cls[v] for v in vic}) == 1  # nosec B101
        vt = max(self.pos[v] for v in vic)
        surv = [p for p in self.pos if p not in vic]
        q1 = (min(self.pos[p] for p in surv) - vt) if surv else 40
        assert _LIMIT + 1 <= c <= _LIMIT + q1, (c, q1)  # nosec B101
        d = c + vt
        if d < 2:
            self.preshift(2 - d)
            d = c + max(self.pos[v] for v in vic)
        self.descend(d)
        below = {p for p, v in self.pos.items() if v < -_LIMIT}
        assert below == vic, (below, vic)  # nosec B101
        self.body.append("pp")
        for p in vic:
            self.pos[p] = 0
        for p in self.pos:
            assert -_LIMIT <= self.pos[p] <= _LIMIT  # nosec B101
        self._land(vic)

    def rise(self, c: int, vids: frozenset[int]) -> None:
        vic = self._vic(vids)
        assert len({self.cls[v] for v in vic}) == 1  # nosec B101
        vb = min(self.pos[v] for v in vic)
        surv = [p for p in self.pos if p not in vic]
        q1 = (vb - max(self.pos[p] for p in surv)) if surv else 40
        assert _LIMIT + 1 <= c <= _LIMIT + q1, (c, q1)  # nosec B101
        u = c - vb
        if u < 2:
            self.preshift(-(2 - u))
            u = c - min(self.pos[v] for v in vic)
        assert min(self.pos.values()) >= -_LIMIT  # nosec B101
        assert all(self.pos[p] + u <= _LIMIT for p in surv)  # nosec B101
        self.body.append("p" + self._sub(u) + "p")
        for p in self.pos:
            self.pos[p] += u
        over = {p for p, v in self.pos.items() if v > _LIMIT}
        assert over == vic, (over, vic)  # nosec B101
        # Any next command's pre-check resets the victims; one ``s`` makes
        # that flush explicit and costs a uniform -2 everyone absorbs.
        self.body.append("s")
        for p in vic:
            self.pos[p] = 0
        for p in self.pos:
            self.pos[p] -= 2
        self._land(vic)

    def _land(self, vic: set[_FoldKey]) -> None:
        val = self.pos[next(iter(vic))]
        new = frozenset(
            x for v in vic for x in (v if isinstance(v, frozenset) else [v])
        )
        c = self.cls[next(iter(vic))]
        absorbed = [p for p in self.pos if p not in vic and self.pos[p] == val]
        for o in absorbed:
            assert self.cls[o] == c, "cross-class landing"  # nosec B101
            new = new | (o if isinstance(o, frozenset) else frozenset([o]))
        for v in set(vic) | set(absorbed):
            del self.pos[v], self.cls[v]
        self.pos[new] = val
        self.cls[new] = c

    def byte(self, p: _FoldKey) -> int:
        return _BYTE_ONE if self.cls[p] == "1" else _BYTE_ZERO

    def finish(self) -> None:
        """Set the one residue that matters and align the print.

        Two points remain, one per class (or one, for a constant table).
        Their final gap must be congruent to the difference of their answer
        bytes; the last relocation of the upper point has the whole
        lower-point gap as its window, which spans a full residue system
        once the gap exceeds 257, so exactly one amount in it qualifies.
        A uniform tail shift then puts the pair onto the bytes themselves.
        """
        if len(self.pos) == 1:
            p = next(iter(self.pos))
            t = (self.byte(p) - self.pos[p]) % 256
            room = _LIMIT - self.pos[p]
            while t > room:
                t -= 256
            self.preshift(t)
        else:
            pts = sorted(self.pos, key=lambda q: self.pos[q])
            lo, hi = pts
            if self.pos[hi] - self.pos[lo] < 258:
                self.preshift(-(self.pos[lo] + 2600))
                u1 = max(_LIMIT + 1 - self.pos[hi], 2)
                assert self.pos[lo] + u1 <= _LIMIT  # nosec B101
                self.body.append("p" + self._sub(u1) + "ps")
                for p in self.pos:
                    self.pos[p] += u1
                assert self.pos[hi] > _LIMIT  # nosec B101
                assert self.pos[lo] <= _LIMIT  # nosec B101
                self.pos[hi] = 0
                for p in self.pos:
                    self.pos[p] -= 2
                pts = sorted(self.pos, key=lambda q: self.pos[q])
                lo, hi = pts
            gap = self.pos[hi] - self.pos[lo]
            assert gap >= 258, gap  # nosec B101
            need = (-(self.byte(hi) - self.byte(lo)) - self.pos[lo]) % 256
            umin = max(_LIMIT + 1 - self.pos[hi], 2)
            umax = _LIMIT - self.pos[lo]
            u = next(
                (c0 for c0 in range(umin, umax + 1) if c0 % 256 == need),
                None,
            )
            assert u is not None, (umin, umax, need)  # nosec B101
            self.body.append("p" + self._sub(u) + "ps")
            for p in self.pos:
                self.pos[p] += u
            assert self.pos[hi] > _LIMIT  # nosec B101
            assert self.pos[lo] <= _LIMIT  # nosec B101
            self.pos[hi] = 0
            for p in self.pos:
                self.pos[p] -= 2
            pts = sorted(self.pos, key=lambda q: self.pos[q])
            lo, hi = pts
            t = (self.byte(hi) - self.pos[hi]) % 256
            room = _LIMIT - self.pos[hi]
            # Unreachable here, unlike in the one-point branch above: the
            # block just put ``hi`` at 0 and then shifted everything down
            # by 2, so ``room`` is exactly ``_LIMIT + 2`` while ``t`` is a
            # residue mod 256.  255 < 3005, so the lift never fires.  The
            # loop stays because the one-point branch's does, and the two
            # read as one rule.
            while t > room:  # pragma: no cover - room is _LIMIT + 2 > 255
                t -= 256
            self.preshift(t)
        for p in self.pos:
            assert self.pos[p] % 256 == self.byte(p) % 256, (  # nosec B101
                self.pos[p],
                self.cls[p],
            )
            assert self.pos[p] <= _LIMIT  # nosec B101
        self.body.append("e")


def _fold_uniform(n: int, step: int) -> tuple[int, ...]:
    """Return the uniform ladder as a weight vector: ``acc = -step * r``."""
    return tuple(step * 2 ** (n - 1 - i) for i in range(n))


def _fold_setters(n: int, weights: tuple[int, ...]) -> list[tuple[str, str]]:
    """One subtracting branch per input; the hold matches it in width.

    Input ``i`` subtracts ``weights[i]`` when its bit is 1 and holds when it
    is 0.  Both branches must come out the same width or the program leaks
    its inputs through ``len()``.

    ``s`` subtracts 2, so an amount that is a multiple of 4 spells at an even
    width and the hold is that many ``p``.  The narrow ladder
    (:data:`_FOLD_NARROW_STEP`) gives its last input an amount of 2, whose
    cheapest spelling ``"s"`` is one character wide -- and **the identity has
    no odd-width spelling at all**, searched exhaustively over ``s``/``i``/
    ``p``/``m`` through width 6: an odd number of the only sign-flipping
    command cannot compose to ``+0``.  So a lone ``s`` can never be padded to
    match a hold, and the subtraction is *respelled* wider instead --
    ``iipssp`` subtracts 2 in six characters, against ``pppppp`` holding --
    which is the same respelling move :func:`_pad_pair`'s odd-gap refusal
    forces elsewhere in this module.

    **Two respellings, on disjoint ranges.**  The overshoot above negates,
    so it dies once ``amount`` reaches the reset line; a pure descent that
    trades ``s`` for ``i`` never rises and so has no such ceiling, but it
    has no even-width form for 1, 2, 3 or 7.  Between them every amount up
    to ``2 * _LIMIT + 2`` spells, which is the whole range a setter can be
    asked for -- positions span ``+-_LIMIT``, so the widest gap is 6006 and
    :func:`_interleaved_fold` asks for ``span + 2``.
    """
    out = []
    for i in range(n):
        amount = weights[i]
        assert amount > 0, amount  # nosec B101
        code = _sub_code(amount)
        if code is not None and len(code) % 2 == 0:
            out.append(("p" * len(code), code))
            continue
        # Odd (or unspellable) width: no hold exists there, so subtract the
        # same amount at the next even width.  Overshoot by ``k`` and add it
        # back through a ``p``-wrapped subtraction,
        # ``sub(amount + k) + "p" + sub(k) + "p"``.  This is the shorter of
        # the two respellings, but it only works while ``amount + k`` stays
        # inside the reset line; the descent below covers the rest.
        #
        # ``_sub_code`` alone never gets there: it spells with as many ``s``
        # as it can, so both halves shrink together and the total width stays
        # odd for every ``k``.  Spending ``i`` -- which subtracts 3, so two of
        # them move 6 in two characters where three ``s`` would take three --
        # is what changes the parity.  ``iipssp`` is the case that matters:
        # ``ii`` subtracts 6, ``pssp`` adds 4 back, six characters for a net
        # of 2, against ``pppppp`` holding.
        spellings = [
            over + "p" + back + "p"
            for over_i in range(5)
            for back_i in range(5)
            for k in range(2, 14)
            if (over := _sub_with(amount + k, over_i)) is not None
            and (back := _sub_with(k, back_i)) is not None
            and len(over + back) % 2 == 0
        ]
        widened = min(
            (c for c in spellings if _apply(0, c) == -amount), key=len, default=None
        )
        if widened is None:
            # The overshoot negates, and from 3002 up that is fatal: ``p``
            # leaves the accumulator at ``+(amount + k)``, above the 3003
            # reset line, so the next command zeroes it and the add-back
            # nets ``+k`` instead of ``-amount``.  Every one of the 1504
            # amounts in 3002..6008 fails that way, and ``span + 2`` in
            # :func:`_interleaved_fold` reaches them once the spread hits
            # 3000 -- where this used to raise rather than decline.
            #
            # Trading ``s`` for ``i`` at the amount itself needs no ``p``:
            # it only ever descends, so the reset cannot fire at any
            # magnitude.  Two ``i`` for three ``s`` moves the same 6 in one
            # character less, which is what reaches the other parity.  It
            # is tried second because the overshoot is the shorter spelling
            # where both apply, and every template that builds today is
            # built on it -- 1, 2, 3 and 7 have no even-width descent at
            # all and are exactly the amounts that still need it.
            widened = min(
                (
                    code
                    for threes in range(8)
                    if (code := _sub_with(amount, threes)) is not None
                    and len(code) % 2 == 0
                    and _apply(0, code) == -amount
                ),
                key=len,
                default=None,
            )
        assert widened is not None, amount  # nosec B101
        assert _apply(0, widened) == -amount, (amount, widened)  # nosec B101
        out.append(("p" * len(widened), widened))
    return out


def _fold(truth_table: str, n: int) -> str | None:
    """Build a fold template, or ``None`` if no plan is found.

    The constructions above all place every row's value in a single pass
    and read the table's structure off a weighting, which is what bounded
    the deep band at five inputs: an additive weighting has ``n`` degrees
    of freedom against ``2**n`` residue constraints.  The fold instead
    treats the program as a sequence of *relocations*.  Rows start on a
    rigid ladder (``acc = -4r``); each wipe -- push a group over the reset
    line, top or bottom -- relocates it by exactly ``3004 + slack``, where
    the slack is bounded by the gap to its nearest survivor; the doubling
    ``m`` regrows gaps past 3004, which is what lets a landing split two
    survivors and change the groups' cyclic order (wipes alone cap the
    spread at 3003 and provably never can); and rows of one class are
    merged by landing them on the same value, which erases their history.
    The plan is found by search, but the emitted program is *checked*, not
    trusted: every step is mirrored on all ``2**n`` rows and asserted.

    Only the final two points carry a residue requirement -- their gap must
    be congruent to the difference of the answer bytes mod 256 -- and the
    last relocation's window spans a full residue system, so the residue
    work needs no weighting at all.  That is why the fold has no arity wall
    of its own below the workspace bound: the ladder must fit inside the
    6006 values a ``p`` can traverse.

    **Three ladders are tried**, and which one serves is what sets the reach
    -- see :func:`_fold_ladders`.  The two uniform spacings come first
    because every template that builds today is built on them; the packed
    ladder (:data:`_FOLD_SUBSET_LADDER`) is the fallback, and it is what
    carries eleven inputs, spending only the ``2**n + 1`` that distinctness
    costs against the uniform ladder's ``2 * (2**n - 1)``.

    Reach, measured rather than argued: every table at ``n <= 4``
    exhaustively, and samples at five through **eleven** that build and print
    correctly on the shipped interpreter.  Twelve is where the construction
    stops, and the end is *structural*: no ladder laying ``2**12`` distinct
    positions spans less than 4095, the doubling is offered only under a
    spread of 3002, and without the doubling the groups' cyclic order is
    provably invariant -- the search from such a state exhausts after fifteen
    states rather than running out of budget.
    """
    for weights in _fold_ladders(n):
        built = _fold_at(truth_table, n, weights)
        if built is not None:
            return built
    return None


def _fold_ladders(n: int) -> list[tuple[int, ...]]:
    """Return the ladders to try, in order, for an ``n``-input table.

    The two uniform ones come first because every template that already
    builds is built on them, so trying anything else ahead would rewrite
    output for tables that need no help.  The subset-sum ladder is the
    fallback that lifts the arity: see :data:`_FOLD_SUBSET_LADDER`.
    """
    out = [_fold_uniform(n, _FOLD_STEP), _fold_uniform(n, _FOLD_NARROW_STEP)]
    packed = _fold_subset_weights(n)
    if packed is not None:
        out.append(packed)
    return out


def _fold_subset_weights(n: int) -> tuple[int, ...] | None:
    """Return the packed distinct-subset-sum ladder, or ``None`` past its reach.

    See :data:`_FOLD_SUBSET_LADDER` for why this shape, and why ``2**n + 1``
    is the floor any such ladder pays.  ``n >= 2`` throughout: the fold is
    only ever reached above two inputs.
    """
    # The tail starts one past the head's total, which is what keeps every
    # subset sum distinct: a power exceeding the sum of everything below it
    # can never be matched by them.
    head = _FOLD_SUBSET_LADDER
    start = sum(head) - 1
    weights = (*head, *(start * 2**i for i in range(n - len(head))))
    return weights if sum(weights) <= _LIMIT else None


def _cofactor_class(truth_table: str, n: int, row: int, laid: int) -> str:
    """Return ``row``'s suffix cofactor after the first ``laid`` inputs.

    An interleaved build may merge two accumulator values only when every
    completion of their unlaid inputs has the same answer.  The substring is
    that exact future function; using the final output bit here would merge
    rows that a later placeholder still has to separate.
    """
    width = 2 ** (n - laid)
    prefix = row >> (n - laid)
    return truth_table[prefix * width : (prefix + 1) * width]


def _cofactor_done(state: _FoldState) -> bool:
    """Whether one wiped point remains for every live suffix cofactor."""
    return all(span == 0 for _, span, _, _ in state) and len(
        {cls for _, _, cls, _ in state}
    ) == len(state)


def _fold_to_cofactors(state: _FoldState, cap: int = 50_000) -> list[_FoldOp] | None:
    """Merge equal suffix cofactors, leaving distinct ones separate.

    This is deliberately a small-state bridge, not the old full-fold search:
    it is used between placeholders, where equal cofactors have already
    reduced the live state.  The final two-answer reduction still goes through
    :func:`_fold_plan`.  Keeping this bounded makes an interleaved candidate a
    fallback rather than a new source of unbounded generator latency.

    ``cap`` bounds the number of states explored, not their *size*, and the
    cost of one state grows with it: a 512-point state exhausts the cap in
    192s, against milliseconds for the handful of points a bridge actually
    uses.  That is the whole of the generator's latency past nine inputs --
    a twelve-input table that no ladder serves spent 133s here before
    refusing, and a *successful* build never pays it.

    So the size is bounded too, which costs no reach.  Exhaustively over
    ``n <= 4`` -- 33628 tables build -- no successful build ever hands this
    a state above eight points, and the constructed adversaries that grow
    the state on purpose (a function of only the first ``k`` inputs embedded
    at ``n = 8, 10, 12``, and a middle window whose growth starts late) top
    out at four.  A larger state does occasionally still solve, but only
    inside builds that go on to fail for other reasons, and a miss here
    aborts the candidate outright, so refusing them changes no output --
    only how fast a doomed arity gives up.  This is the "compactable
    intermediate states" the bridge is documented to accept, made explicit.
    """
    import heapq

    start = _fold_norm(list(state))
    if _cofactor_done(start):
        return []
    if len(start) > _COFACTOR_BRIDGE_POINTS:
        return None
    seen = {_fold_sig(start)}
    counter = 0
    heap: list[tuple[int, int, int, _FoldState, list[_FoldOp]]] = [
        (len(start), 0, 0, start, [])
    ]
    while heap and len(seen) <= cap:
        _, depth, _, current, ops = heapq.heappop(heap)
        for kind, k, amount, rows, nxt in _fold_moves(current, kcap=None):
            signature = _fold_sig(nxt)
            if signature in seen:
                continue
            next_ops = [*ops, (kind, k, amount, rows)]
            if _cofactor_done(nxt):
                return next_ops
            seen.add(signature)
            counter += 1
            heapq.heappush(heap, (len(nxt), depth + 1, counter, nxt, next_ops))
    return None


def _interleaved_fold(truth_table: str, n: int) -> str | None:
    """Try a placeholder/fold/placeholder build before the all-row fallback.

    Every ``{Xi}`` appears once and in name order, but unlike :func:`_fold_at`
    its setter is emitted immediately before the cofactor fold it enables.
    The emitter mirrors every raw row, so a returned candidate is checked at
    every reset and landing just like the shipped ladder path.

    The current bridge deliberately accepts only compactable intermediate
    states; it is an executable replacement skeleton, not yet the large-state
    gap controller.  A miss simply lets the established fold try its ladders.
    """
    setters: list[tuple[str, str]] = []
    rows = frozenset(range(2**n))
    emitter = _FoldEmitter.__new__(_FoldEmitter)
    emitter.table = truth_table
    emitter.rows = 2**n
    emitter.pos = {rows: 0}
    emitter.cls = {rows: truth_table}
    emitter.body = []

    for index in range(n):
        # A live cofactor that takes the same suffix on both branches does not
        # need a new rung at all.  More importantly, identity branches keep a
        # late ignored input from re-expanding a compacted state merely to
        # collapse it again.  Where a split remains, one current span plus a
        # gap of two keeps the 0 and 1 bands disjoint without paying a global
        # binary weight for inputs already folded away.
        splits = False
        for group_key in emitter.pos:
            raw = set(group_key) if isinstance(group_key, frozenset) else {group_key}
            children = {_cofactor_class(truth_table, n, row, index + 1) for row in raw}
            if len(children) > 1:
                splits = True
                break
        if splits:
            span = max(emitter.pos.values()) - min(emitter.pos.values())
            zero, one = _fold_setters(1, (span + 2,))[0]
        else:
            zero = one = "pp"
        setters.append((zero, one))
        next_pos: dict[_FoldKey, int] = {}
        next_cls: dict[_FoldKey, str] = {}
        # A previously merged cofactor splits only on this input.  Rows taking
        # the same branch retain one identical suffix cofactor, which is the
        # inductive fact the merge below asserts rather than assumes.
        by_value: dict[tuple[int, str], set[int]] = {}
        for group_key, value in emitter.pos.items():
            raw = set(group_key) if isinstance(group_key, frozenset) else {group_key}
            for bit in (0, 1):
                picked = {row for row in raw if (row >> (n - 1 - index)) & 1 == bit}
                if not picked:
                    continue
                code = one if bit else zero
                new_value = _apply(value, code)
                if not -_LIMIT <= new_value <= _LIMIT:
                    return None
                suffixes = {
                    _cofactor_class(truth_table, n, row, index + 1) for row in picked
                }
                if len(suffixes) != 1:
                    return None
                cls = next(iter(suffixes))
                by_value.setdefault((new_value, cls), set()).update(picked)
        # A position collision across unequal cofactors would erase a future
        # distinction before the planner can see it.
        occupied: dict[int, str] = {}
        for (value, cls), raw in by_value.items():
            if value in occupied and occupied[value] != cls:
                return None
            occupied[value] = cls
            coalesced_key: _FoldKey = (
                next(iter(raw)) if len(raw) == 1 else frozenset(raw)
            )
            next_pos[coalesced_key] = value
            next_cls[coalesced_key] = cls
        emitter.pos, emitter.cls = next_pos, next_cls
        emitter.body.append("{X" + str(index) + "}")

        items = [
            (value, 0, cls, key if isinstance(key, frozenset) else frozenset({key}))
            for key, value in emitter.pos.items()
            for cls in [emitter.cls[key]]
        ]
        partial = _fold_to_cofactors(_fold_norm(items))
        if partial is None:
            return None
        for kind, _, amount, row_ids in partial:
            if kind == "m":
                emitter.double(next_is_rise=False)
            elif kind == "d":
                emitter.dive(amount, row_ids)
            else:
                emitter.rise(amount, row_ids)

    final_items = [
        (value, 0, cls, key if isinstance(key, frozenset) else frozenset({key}))
        for key, value in emitter.pos.items()
        for cls in [emitter.cls[key]]
    ]
    # After the last placeholder a suffix is one answer bit, so the existing
    # two-class plan and residue endgame apply unchanged.
    final = _fold_plan(_fold_norm(final_items))
    if final is None:
        return None
    for kind, _, amount, row_ids in final:
        if kind == "m":
            emitter.double(next_is_rise=False)
        elif kind == "d":
            emitter.dive(amount, row_ids)
        else:
            emitter.rise(amount, row_ids)
    emitter.finish()
    header = ";".join(
        f"{index}={zero}|{one}" for index, (zero, one) in enumerate(setters)
    )
    return header + _HEADER_END + "".join(emitter.body)


#: A two-sided ladder was built and **removed once measured**, the same way
#: the positive-ladder band was.  One weight is made negative -- an *adding*
#: setter, spelled ``p sub(k) p``, whose inner subtraction must come out even
#: so the ``p``-repeated hold is an identity rather than a negation -- which
#: moves half the rows above zero.  That doubles the *positions* available,
#: ``[-_LIMIT, _LIMIT]`` rather than ``[-_LIMIT, 0]``, and at twelve inputs
#: it lays 4096 distinct rows peaking at 2050, comfortably inside 3003.
#:
#: It still serves nothing, because **positions are not the binding
#: resource**: the plan needs the state's *span*, and 4096 distinct integers
#: span at least 4095 wherever they sit.  A wipe relocates by at least 3004
#: and the guard refuses a state spanning more than ``2 * _LIMIT``, so a
#: 4099-wide start has only two legal moves and the descent dies at once;
#: the doubling is offered only under ``spread * 2 <= 2 * _LIMIT - 2``, which
#: a span past 3002 can never satisfy, and the doubling is what this module
#: proves is needed to reorder groups at all.  Measured: 0 of 18 tables
#: across five arities are served by the straddle ladder and not by the
#: packed one.  Straddling therefore buys room the construction cannot spend.


def _fold_positions(n: int, weights: tuple[int, ...]) -> list[int]:
    """Where each row's accumulator sits after the setters have run.

    Input ``i`` subtracts ``weights[i]`` when its bit is 1, so row ``r`` lands
    on minus the sum of the weights its bits select.  The uniform ladder is
    the special case ``weights[i] == step * 2 ** (n - 1 - i)``, which is what
    makes row order and position order agree there; a general weighting
    breaks that, which is why callers must sort.
    """
    out = []
    for r in range(2**n):
        total = 0
        for i in range(n):
            if (r >> (n - 1 - i)) & 1:
                total += weights[i]
        out.append(-total)
    return out


def _fold_at(truth_table: str, n: int, weights: tuple[int, ...]) -> str | None:
    """Build a fold template on a given ladder, or ``None``.

    **The ladder is gated against ``_LIMIT``, not ``2 * _LIMIT``.**  The plan
    state is relative -- :func:`_fold_moves` allows a *span* of ``2 * _LIMIT``
    because a state may sit anywhere in ``[-_LIMIT, _LIMIT]`` -- but the
    emitter lays the rows at absolute positions starting from a zero
    accumulator, so the ladder itself has to fit in ``[-_LIMIT, _LIMIT]``.
    Gating on the relative bound lets the planner spend thousands of moves on
    a geometry the emitter then refuses on its first op: the alternating
    table at eleven inputs plans 2833 ops on a 4094-wide uniform ladder and
    asserts immediately.

    **Rows are grouped by position, not by row index.**  On a uniform ladder
    the two orders agree, so the original code walked ``range(2**n)`` and
    coalesced neighbours; on a weighted ladder they do not, and grouping by
    index would build a state whose "runs" are not contiguous in the geometry
    the plan reasons about.  Sorting first makes the same construction work
    for both, and the uniform case is unchanged because sorting a ladder that
    is already ordered is the identity.
    """
    pos = _fold_positions(n, weights)
    # Two rows sharing a position are merged before the plan starts and can
    # never be separated again, so every ladder offered is a distinct-sum
    # one.  Asserted rather than guarded: a ladder that collides is a bug in
    # :func:`_fold_ladders`, not a table this construction declines.
    assert len(set(pos)) == len(pos), (n, weights)  # nosec B101
    if max(abs(p) for p in pos) > _LIMIT:
        return None
    order = sorted(range(2**n), key=lambda r: -pos[r])
    runs: list[list[int]] = []
    for r in order:
        if runs and truth_table[runs[-1][-1]] == truth_table[r]:
            runs[-1].append(r)
        else:
            runs.append([r])
    state = [
        (
            pos[rn[0]],
            pos[rn[0]] - pos[rn[-1]],
            truth_table[rn[0]],
            frozenset(rn),
        )
        for rn in runs
    ]
    ops = _fold_plan(_fold_norm(state))
    if ops is None:
        return None
    emitter = _FoldEmitter(truth_table, n, weights)
    for idx, (kind, _, c, vids) in enumerate(ops):
        if kind == "m":
            emitter.double(next_is_rise=(idx + 1 < len(ops) and ops[idx + 1][0] == "u"))
        elif kind == "d":
            emitter.dive(c, vids)
        else:
            emitter.rise(c, vids)
    emitter.finish()
    header = ";".join(
        f"{k}={zero}|{one}" for k, (zero, one) in enumerate(_fold_setters(n, weights))
    )
    placeholders = "".join("{X" + str(k) + "}" for k in range(n))
    return header + _HEADER_END + placeholders + "".join(emitter.body)


#: How many candidate pre-vectors the construction weighs before taking the
#: shortest program among them, and how many spellings of each it prices.
#: Both are budgets on *output length*, not on reachability: the first
#: candidate that solves already computes the table, and every table the
#: model admits is built at ``(1, 1)``.  Measured over the whole three-input
#: arity, ``(12, 6)`` is where no table's program comes out longer than the
#: enumeration this replaced; ``(6, 3)`` leaves four longer, the worst
#: 36 -> 41.
_CANDIDATES = 12
_SPELLINGS = 6

#: Steps between the classes of a pre-vector.  The step decides how far apart
#: the rows sit before the last setter maps them onto the answer values, and
#: a smaller spread spells shorter, so these are tried in the order that
#: tends to produce the shortest program rather than by magnitude alone.
_STEPS = (1, 2, 3, 4, -1, -2, 6, -3, 8, 12, -4)


def _solve_affine(values: tuple[int, ...], wanted: tuple[int, ...]) -> _Branch | None:
    """Solve ``a * v + b == p`` over the grid, or ``None`` if unsolvable.

    Two points determine a line, so this divides rather than searches: the
    first pair of entries with distinct ``values`` fixes the multiplier, the
    offset follows, and the rest are checked.  Constant ``values`` leave the
    multiplier free, and then the first that spells an in-grid offset wins.
    """
    anchor: tuple[int, int] | None = None
    for value, want in zip(values, wanted, strict=True):
        if anchor is None:
            anchor = (value, want)
        elif value != anchor[0]:
            num, den = want - anchor[1], value - anchor[0]
            if num % den:
                return None
            a = num // den
            b = anchor[1] - a * anchor[0]
            if a not in _WIDE_A_VALS or b not in _WIDE_B_VALS:
                return None
            fits = all(a * x + b == p for x, p in zip(values, wanted, strict=True))
            return (a, b) if fits else None
    if anchor is None or len(set(wanted)) != 1:
        return None
    for a in _WIDE_A_VALS:
        b = wanted[0] - a * anchor[0]
        if b in _WIDE_B_VALS:
            return (a, b)
    return None


def _realisations(
    values: tuple[int, ...],
) -> list[tuple[_Branch, _Branch, _Branch]]:
    """Every way the first two setters produce ``values``.

    The first setter runs on a zero accumulator, so its two branches
    contribute only their offsets ``(p, q)``.  The second maps those by
    ``(a, c)`` and ``(b, d)``, giving
    ``values = (a*p + c, b*p + d, a*q + c, b*q + d)``.  Differencing the
    entries that share a branch leaves ``values[0] - values[2] = a*(p - q)``
    and ``values[1] - values[3] = b*(p - q)``, so once the first setter's
    offsets are chosen the multipliers are divisions and the second setter's
    offsets follow.  Nothing here enumerates programs.
    """
    out: list[tuple[_Branch, _Branch, _Branch]] = []
    first, second = values[0] - values[2], values[1] - values[3]
    for p in _WIDE_B_VALS:
        for q in _WIDE_B_VALS:
            gap = p - q
            if gap == 0:
                if first or second:
                    continue
                for a in _WIDE_A_VALS:
                    c = values[0] - a * p
                    if c not in _WIDE_B_VALS:
                        continue
                    for b in _WIDE_A_VALS:
                        d = values[1] - b * p
                        if d in _WIDE_B_VALS:
                            out.append(((p, q), (a, c), (b, d)))
                continue
            if first % gap or second % gap:
                continue
            a, b = first // gap, second // gap
            if a not in _WIDE_A_VALS or b not in _WIDE_A_VALS:
                continue
            c, d = values[0] - a * p, values[1] - b * p
            if c in _WIDE_B_VALS and d in _WIDE_B_VALS:
                out.append(((p, q), (a, c), (b, d)))
    return out


def _merge_classes(truth_table: str) -> list[int]:
    """Which pre-vector entries may share a value.

    Entry ``j`` carries the rows whose leading bits are ``j``, and the last
    setter maps it by one branch per value of the last input.  Two entries
    holding the same value are therefore mapped alike by *both* branches, so
    they may share only where the table agrees on both of their rows.  That
    makes the pre-vector's partition a reading of the table rather than a
    choice, which is what removes the search.
    """
    even = tuple(int(truth_table[2 * j]) for j in range(4))
    odd = tuple(int(truth_table[2 * j + 1]) for j in range(4))
    groups: list[list[int]] = []
    for j in range(4):
        for group in groups:
            if even[j] == even[group[0]] and odd[j] == odd[group[0]]:
                group.append(j)
                break
        else:
            groups.append([j])
    classes = [0] * 4
    for index, group in enumerate(groups):
        for j in group:
            classes[j] = index
    return classes


def _affine(truth_table: str, n: int) -> str | None:
    """Build a composed-affine template, or ``None`` if the table is not one.

    This is the wide construction above two inputs, and it is **derived**
    rather than searched.  Composing one affine setter per input makes the
    accumulator, after the first two setters, a vector of four values that
    the last setter maps by one branch for each value of the last input --
    so the table's even and odd rows are two affine images of one shared
    vector.  That is exactly the shared-cofactor law, and reading it
    backwards is a construction:

    * :func:`_merge_classes` reads the pre-vector's partition off the table,
      since two entries may share a value only where both of their rows
      agree;
    * choosing values for those classes and calling :func:`_solve_affine`
      twice *solves* the last setter's two branches, two points fixing a
      line;
    * :func:`_realisations` inverts the first two setters by division.

    An enumeration used to stand here instead, composing every branch pair
    layer by layer and deduplicating by induced partition.  It reached the
    same 86 tables -- exhaustively verified, since the dispatch only calls
    this at three inputs -- but cost 6.4 seconds against 0.4 for the whole
    arity and emitted longer programs, because it kept whichever witness
    arrived first rather than the one that spells short.  Its subtlety is
    worth recording even though the code is gone: witnesses sharing a
    partition are *not* interchangeable, since a later setter translates by
    a bounded offset and cannot move a distant vector onto the values a tail
    needs, and selecting them by arrival silently cost two tables.

    Only at three inputs.  The dispatch does not call this above that -- the
    deep band covers every table it would reach there -- so the budgets in
    :data:`_CANDIDATES` and :data:`_SPELLINGS`, which are tuned for program
    length rather than coverage, are measured over the arity this serves.
    """
    if n != 3 or len(set(truth_table)) == 1:
        return None
    classes = _merge_classes(truth_table)
    even = tuple(int(truth_table[2 * j]) for j in range(4))
    odd = tuple(int(truth_table[2 * j + 1]) for j in range(4))
    candidates = sorted(
        (
            max(abs(base + step * classes[j]) for j in range(4)),
            tuple(base + step * classes[j] for j in range(4)),
        )
        for step in _STEPS
        for base in _WIDE_B_VALS
    )
    best: str | None = None
    weighed = 0
    for _, values in candidates:
        if _solve_affine(values, even) is None:
            continue
        if _solve_affine(values, odd) is None:
            continue
        spellings = _realisations(values)
        if not spellings:
            continue
        # Cheapest first: a setter's length follows the magnitude of what it
        # subtracts, so the smallest offsets spell the shortest program.
        spellings.sort(
            key=lambda r: max(abs(r[0][0]), abs(r[0][1]), abs(r[1][1]), abs(r[2][1]))
        )
        for offsets, low, high in spellings[:_SPELLINGS]:
            for one, other in ((1, 0), (0, 1)):
                last_low = _solve_affine(
                    values, tuple(one if bit else other for bit in even)
                )
                last_high = _solve_affine(
                    values, tuple(one if bit else other for bit in odd)
                )
                if last_low is None or last_high is None:
                    continue
                template = _spell_affine(
                    ((0, offsets[0]), (0, offsets[1])),
                    (low, high),
                    (last_low, last_high),
                    one,
                    other,
                )
                if template is not None and (best is None or len(template) < len(best)):
                    best = template
        weighed += 1
        if weighed >= _CANDIDATES:
            break
    return best


def _spell_affine(
    first: tuple[_Branch, _Branch],
    second: tuple[_Branch, _Branch],
    third: tuple[_Branch, _Branch],
    one: int,
    other: int,
) -> str | None:
    """Spell three solved setters as a template, or ``None``.

    Both branches of a setter come out at a width they share, so every
    instantiation has the same length and no program leaks its inputs
    through ``len()``.
    """
    setters = []
    for zero_branch, one_branch in (first, second, third):
        zero_widths = _spellings_by_width(*zero_branch)
        one_widths = _spellings_by_width(*one_branch)
        shared = set(zero_widths) & set(one_widths)
        if not shared:  # pragma: no cover - every grid branch spells at 6 and 7
            # Measured over all 7 * 25 ``(a, b)`` the grid admits: every one
            # of them has a spelling at width 6 and at width 7, so any two
            # branches share at least those.  The guard stays because the
            # grid is a constant that could widen.
            return None
        width = min(shared)
        setters.append((zero_widths[width], one_widths[width]))
    tail = _tail_for(one, other)
    if tail is None:
        return None
    header = ";".join(
        f"{k}={zero}|{one_code}" for k, (zero, one_code) in enumerate(setters)
    )
    body = "".join("{X" + str(k) + "}" for k in range(3)) + tail
    return header + _HEADER_END + body


def pct_squared_minus_one(truth_table: str) -> str:
    """Build a %^2^-1 template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, indexed by the
    inputs (most significant first); the table length implies ``n``.

    %^2^-1 has no usable branch -- ``t`` only ever jumps to position 0 -- so
    this generator computes the answer arithmetically instead of routing a
    decision tree.  Each input contributes one affine map, composed into a
    product-weighted accumulator, and a single ``l`` prints it in decimal.
    The maps are *derived* from the table rather than searched: each column's
    slope is read off the table directly, leaving only the class values to
    place, from which both offsets are solved.

    A one-input table is derived as the two-input table that ignores its
    second input, and the unused setter is then dropped, so ``n == 1`` shares
    the derivation rather than needing a second path.

    Above two inputs the derivation does not apply -- it reads one slope per
    column of a two-input table -- and the other constructions take over, in
    increasing order of program length: :func:`_cascade` for any conjunction
    or disjunction of literals at any arity, :func:`_affine` for the tables
    one affine setter per input composes, :func:`_ladder`, which weights the
    inputs and lets the over-3003 reset read the sum as a threshold,
    :func:`_deep_band`, which prints with ``e`` so residues mod 256 are the
    target and repeated resets cut a weighted order into runs, and
    :func:`_fold`, which drops the weighting altogether and plans
    a sequence of relocations instead -- the path that closes five inputs.
    A table none of them covers raises :class:`ValueError`, because emitting
    nothing is better than emitting a program that computes the wrong
    function.
    """
    n = _validate_truth_table(truth_table)
    if n > 2:
        # Above two inputs the derivation below does not apply -- it reads one
        # slope per column of a two-input table -- but the minterm cascade
        # does, at any arity.  A table it cannot build is still refused rather
        # than served by a program computing the wrong function.
        # The cascade is tried first because it is much the shorter of the
        # two -- ``2n + 4`` characters against the affine path's setters --
        # and it covers every subcube at any arity.
        cascade = _cascade(truth_table, n)
        if cascade is not None:
            return cascade
        # Tables that are not subcubes may still compose from one affine
        # setter per input, which is what reaches XOR at three inputs.
        #
        # Only at three.  This path derives a whole arity at once and its
        # composition frontier grows 90 -> 1630 -> 36458 states at n = 2, 3, 4,
        # so a four-input table costs about two minutes here whether or not it
        # ends up served -- parity-4 was measured at 125s, against 0.01s for the
        # deep band that serves it instead.  The deep band covers every table
        # this path reaches above three inputs, so the enumeration is skipped
        # rather than paid for; at three inputs it stays, where it is instant
        # and its programs are much the shorter.
        if n == 3:
            affine = _affine(truth_table, n)
            if affine is not None:
                return affine
        # Everything above is affine in the accumulator, so it cannot merge
        # rows that do not already agree.  The ladder path is the one that
        # uses the over-3003 reset as a threshold, which is what reaches a
        # majority.  It is tried last because its programs are the longest by
        # far -- hundreds of characters against the others' dozens.
        ladder = _ladder(truth_table, n)
        if ladder is not None:
            return ladder
        # Every path above prints with ``l``, which needs the accumulator to be
        # exactly 0 or 1.  The deep band prints with ``e`` instead -- only the
        # residue mod 256 matters -- and repeated resets cut a weighted order
        # into as many bands as the table has runs.  Its ladder is built by
        # subtraction, so the whole order sits below zero where the reset
        # cannot fire, and rows of one class may collide; that is what makes
        # three and four inputs total.
        deep = _deep_band(truth_table, n)
        if deep is not None:
            return deep
        # The deep band still reads the table's structure off one additive
        # weighting, and from five inputs on every weighting inside the limit
        # collides rows of opposite classes for a generic table.  The fold
        # drops the weighting altogether: it plans a sequence of relocations
        # (each wipe moves a group by exactly 3004 plus a bounded slack, the
        # doubling regrows gaps) that merges each class onto one value, and
        # only the final two-point gap carries a residue requirement -- with
        # a full residue system as its window.  It closes five inputs whole.
        fold = _fold(truth_table, n)
        if fold is None:
            # The staged route is intentionally after the established ladders:
            # at the arities they already serve it is a much longer program,
            # while beyond them it is the only construction that can release
            # equal suffix cofactors before every row has been laid.
            fold = _interleaved_fold(truth_table, n)
        # Reaching this raise means no ladder served: either the plan search
        # and the staged cofactor route both gave up.  The guard stays because
        # emitting nothing is better than emitting a program for the wrong
        # function.
        if fold is None:
            raise ValueError(
                f"%^2^-1 builds every table at one, two, three and four "
                f"inputs, and every table tried from five through eleven; "
                f"beyond those a conjunction or disjunction of literals at "
                f"any arity, the thresholds a weighted ladder crosses, the "
                f"tables a deep band schedules, the tables the all-row fold "
                f"can plan, and the compactable suffix-cofactor stages the "
                f"interleaved fold can plan (the all-row ladder caps it at "
                f"eleven inputs); "
                f"got {n} inputs ({truth_table!r})"
            )
        return fold
    # Widen a one-input table by repeating each entry, so the second input is
    # present in the derivation but cannot change the answer.
    widened = truth_table if n == 2 else "".join(bit * 2 for bit in truth_table)
    derived = _derive(widened)
    # Every one- and two-input table derives -- the enumeration always
    # finds a realisable parameter set -- so a miss is a bug in the
    # derivation rather than a table this generator cannot serve.
    if derived is None:
        raise AssertionError(f"no %^2^-1 derivation for truth table {truth_table!r}")
    setters, tail = derived
    if n == 1:
        # A widened table cannot depend on its second input, so that setter's
        # two branches carry the same code; fold it into the tail and keep one
        # placeholder.  The equality is checked rather than assumed, because
        # silently dropping a branch that *did* differ would emit a program
        # for the wrong function.
        zero, one = setters[1]
        # The widened table repeats each entry, so input 1 cannot change
        # the answer and its two branches must come out identical.
        if zero != one:
            raise AssertionError(
                f"one-input derivation split on input 1: {truth_table!r}"
            )
        setters, tail = setters[:1], zero + tail
    header = ";".join(f"{k}={zero}|{one}" for k, (zero, one) in enumerate(setters))
    body = "".join("{X" + str(k) + "}" for k in range(n)) + tail
    return header + _HEADER_END + body


def fill(template: str, bits: list[int]) -> str:
    """Instantiate ``template`` for ``bits``, returning a runnable program.

    The header names each setter's two branches; this strips it and replaces
    every ``{Xi}`` with the branch that input's bit selects.  The branches
    are equal width, so every instantiation has the same length whatever the
    inputs.
    """
    header, _, body = template.partition(_HEADER_END)
    branches = {
        int(m.group(1)): (m.group(2), m.group(3)) for m in _DECL_RE.finditer(header)
    }
    for index, bit in enumerate(bits):
        zero, one = branches[index]
        body = body.replace("{X" + str(index) + "}", one if bit else zero)
    return body
