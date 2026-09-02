r"""Parameterized boolean generator for %^2^-1.

``%^2^-1`` has one accumulator and one control-flow command, ``t``, which
rewinds to the start of the program while the accumulator is nonzero.  There
is no forward jump and no skip, so a program that *reads* its inputs cannot
branch on them: ``Esolangs.PctBooleanWall`` proves in Lean that no such
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
does, but *searches* the composition instead of reading slopes off columns,
so it is not restricted to two inputs.  Two things make that search finite:
states are deduplicated by the **partition** they induce on the input
combinations rather than by their values, since only which combinations share
an accumulator decides the table; and each setter's two branches are spelled
at a common width by :func:`_spellings_by_width` rather than padded, which is
what lets an odd width gap close.  That gap was the binding constraint --
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
five.  The fold is not *proved* total, and its own workspace bound (the row
ladder must fit the 6006 values a ``p`` can traverse) gives out above ten
inputs.

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
Lean wall in ``Esolangs.PctBooleanWall`` covers the reading model only, and
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

#: Distinct value vectors kept per induced partition.  One is too few: the
#: first witness found for parity-3 has no equal-width spelling while a
#: sibling with the same partition does.  Keying on the full vector instead
#: explodes the frontier, and the count stops mattering past four -- measured
#: 82 tables at two witnesses, 84 at four, and 84 at every count up to
#: sixteen.
_WITNESSES = 6


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


def _match_pair(
    branch_zero: tuple[int, int], branch_one: tuple[int, int]
) -> tuple[str, str] | None:
    """Spell a setter's two branches at a common width, or ``None``.

    The narrowest shared width is taken, so the setter is as short as this
    construction makes it -- though not necessarily the shortest program for
    the table, since the branches are chosen before the tail is known.

    The empty-intersection return is never taken for the shipped grid: all
    30625 branch pairs over :data:`_WIDE_A_VALS` x :data:`_WIDE_B_VALS` share
    a width, and every map in it has some spelling.  It is kept because that
    is a property of the grid and the depth, not of the function -- narrowing
    either would make it fire -- and returning ``None`` is what lets
    :func:`_affine_tables` skip a state rather than emit a setter whose two
    branches differ in length, which would leak the input through ``len()``.
    """
    zero = _spellings_by_width(*branch_zero)
    one = _spellings_by_width(*branch_one)
    shared = sorted(set(zero) & set(one))
    if not shared:  # pragma: no cover - no pair in the shipped grid lacks one
        return None
    width = shared[0]
    return zero[width], one[width]


def _partition(vec: tuple[int, ...]) -> tuple[int, ...]:
    """Relabel a vector by first appearance, keeping only its equality pattern.

    The tail separates two classes, so what decides the table is which input
    combinations share an accumulator value, not the values themselves.
    Deduplicating on the pattern keeps the frontier flat across layers; an
    earlier sweep that deduplicated on values instead did not finish, and one
    that capped the values reported *fewer* tables than the cascade already
    builds -- the signature of a truncated search rather than a result.
    """
    seen: dict[int, int] = {}
    return tuple(seen.setdefault(v, len(seen)) for v in vec)


def _reindex(vec: tuple[int, ...], n: int) -> tuple[int, ...]:
    """Reorder a composed vector into truth-table index order.

    :func:`_compose` appends each input's results as ``zero + one``, so input
    ``k`` lands in bit ``k`` of the index and the *last* input is most
    significant.  A truth table indexes the other way round, most significant
    first.  The two are a bit reversal; composing without correcting it
    harvests a permuted table, which shows up as inverted outputs on setters
    that do not even differ.
    """
    out = [0] * len(vec)
    for index, value in enumerate(vec):
        combo = 0
        for k in range(n):
            combo |= ((index >> k) & 1) << (n - 1 - k)
        out[combo] = value
    return tuple(out)


#: One branch of a setter as an affine map, ``(a, b)`` for ``x -> a*x + b``.
_Branch = tuple[int, int]

#: A setter: the branch taken when the input is 0, and when it is 1.
_Setter = tuple[_Branch, _Branch]

#: A composition state: the accumulator per input combination, paired with the
#: setters that produced it.
_State = tuple[tuple[int, ...], tuple[_Setter, ...]]


def _compose(n: int) -> list[_State]:
    """Every accumulator vector one affine setter per input can produce.

    Enumerating setter *assignments* is a product over inputs and blows up.
    Only the value vector carries from one input to the next, so the layers are
    composed with deduplication instead: start from the accumulator's initial
    zero and, at each input, apply every branch pair to every vector kept so
    far.  That is a fixpoint over vectors rather than a product over programs.

    The affine model ignores the over-3003 reset, which is sound only while the
    values stay small.  With ``|a| <= 4`` and ``|b| <= 12`` over three layers
    the magnitude cannot exceed ``4*(4*(4*0 + 12) + 12) + 12 == 252``, far
    under the limit, so no reset fires inside a setter and the composition is
    exactly what the interpreter computes.  A wider arity must re-derive this
    before trusting the model.
    """
    branches: list[_Branch] = [(a, b) for a in _WIDE_A_VALS for b in _WIDE_B_VALS]
    frontier: list[_State] = [((0,), ())]
    for _ in range(n):
        layer: dict[tuple[int, ...], list[_State]] = {}
        for vec, assign in frontier:
            for zero_branch in branches:
                zero = tuple(zero_branch[0] * v + zero_branch[1] for v in vec)
                for one_branch in branches:
                    one = tuple(one_branch[0] * v + one_branch[1] for v in vec)
                    candidate = zero + one
                    bucket = layer.setdefault(_partition(candidate), [])
                    if len(bucket) < _WITNESSES and all(
                        candidate != seen for seen, _ in bucket
                    ):
                        bucket.append((candidate, (*assign, (zero_branch, one_branch))))
        frontier = [state for bucket in layer.values() for state in bucket]
    return frontier


@cache
def _affine_tables(n: int) -> dict[str, tuple[tuple[tuple[str, str], ...], str]]:
    """Every table the composed-affine path builds at ``n`` inputs.

    Derived for a whole arity in one pass and cached, because the composition
    is shared: the states already carry the table each one induces, so
    harvesting them costs one sweep rather than one per table.
    """
    built: dict[str, tuple[tuple[tuple[str, str], ...], str]] = {}
    for raw, assign in _compose(n):
        vec = _reindex(raw, n)
        values = set(vec)
        if len(values) != 2:
            continue
        for one_value in values:
            table = "".join("1" if v == one_value else "0" for v in vec)
            if table in built:
                continue
            zero_value = next(v for v in vec if v != one_value)
            tail = _tail_for(one_value, zero_value)
            if tail is None:
                continue
            setters = [_match_pair(zero, one) for zero, one in assign]
            # Unreachable for the shipped grid, where every branch pair shares
            # a width -- see :func:`_match_pair`.  It stays because a narrower
            # grid or a shallower spelling depth would make it fire, and
            # skipping the state is what keeps a setter from being emitted
            # with branches of different lengths.
            if any(pair is None for pair in setters):  # pragma: no cover
                continue
            # ``mypy`` cannot see the guard above, which is what makes the
            # cast safe rather than assumed.
            built[table] = (
                tuple(pair for pair in setters if pair is not None),
                tail,
            )
    return built


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
            break
        rest = order[prefix:]
        if not rest:
            break
        if max(values[r] for r in rest) - min(values[r] for r in rest) > _LIMIT:
            continue
        high = _LIMIT - max(values[r] for r in rest)
        low = (_LIMIT - min(values[r] for r in order[:prefix]) + 1) if prefix else 0
        low = max(low, 0)
        if low > high:
            continue
        drop = next(
            (
                d
                for d in range(low, min(high, low + _BAND_UNIT) + 1)
                if _sub_code(d) is not None
            ),
            None,
        )
        if drop is None:
            continue
        body = _deep_body(truth_table, n, values, order, anchor, live, prefix, drop)
        if body is not None:
            return body
    return None


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
        return None
    cleared = set(order[:prefix])
    for row in cleared:
        current[row] = 0

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
            return None
        low = _LIMIT - min(current[r] for r in wipe) + 1
        high = _LIMIT - max(current[r] for r in keep)
        if low > high or low <= 0:
            return None
        band = _BYTE_ONE if truth_table[wipe[0]] == "1" else _BYTE_ZERO
        # A wiped band thereafter takes the same translations as the survivors,
        # so the parking cancels from their gap and one congruence fixes the
        # cut: the translation is solved, not searched.
        wanted = (live - band - current[anchor]) % _BAND_UNIT
        up = low + ((wanted - low) % _BAND_UNIT)
        if up > high:
            return None
        raise_code = _affine_code(1, up)
        if raise_code is None:
            return None
        raised = {r: _apply(v, raise_code + "s") for r, v in current.items()}
        down = _DEEP_PARK - max(raised.values())
        park = _affine_code(1, down)
        if park is None:
            return None
        parked = {r: _apply(v, park) for r, v in raised.items()}
        if max(parked.values()) > _LIMIT:
            return None
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
            continue
        printed = {r: _apply(v, tail) for r, v in current.items()}
        if all(
            (printed[r] & 0xFF) == (_BYTE_ONE if truth_table[r] == "1" else _BYTE_ZERO)
            for r in rows
        ):
            return body + tail + "e"
    return None


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
    for units in sorted(
        product(range(_DEEP_CAP + 1), repeat=n), key=lambda u: (sum(u), max(u), u)
    ):
        if not any(units):
            continue
        for mask in range(2**n):
            values = _deep_values(n, units, mask)
            body = _deep_plan(truth_table, n, values)
            if body is None:
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

#: One point of a fold plan: ``(top, span, cls, rows)`` -- the group's highest
#: row value relative to the state's top, how far its rows extend below it
#: (0 once it has been wiped and its rows merged), its class, and the rows.
_FoldPoint = tuple[int, int, str, frozenset[int]]
_FoldState = tuple[_FoldPoint, ...]

#: One move: ``(kind, k, c, victims)`` -- ``"m"`` doubles, ``"d"``/``"u"``
#: wipe the bottom/top ``k`` groups with relocation amount ``c``.
_FoldOp = tuple[str, int, int, frozenset[int]]

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
    state: _FoldState, maxdepth: int = 40, cap: int = 2_000_000
) -> list[_FoldOp] | None:
    """Best-first search to a two-point state, or ``None``.

    States are keyed by their relative geometry -- ids do not matter for
    reachability -- and ranked by point count first, so contractions are
    pursued before excursions.
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
    target: int = 8,
    width: int = 48,
    maxsteps: int = 90,
) -> list[_FoldOp] | None:
    """Beam-reduce a wide state down to ``target`` points, or ``None``.

    Near-parity tables have up to 32 runs and the exhaustive search drowns
    there; a narrow beam ranked by point count finds the reduction pattern
    (it is nearly forced) and hands the small remainder to the search.

    The target is 8 rather than the state width at which the search *starts*
    to struggle, and the difference is not cosmetic: at 21 points the search
    explores for fifty seconds and then gives up, while beaming the same
    state to 8 takes 0.37s and the search finishes it instantly.  A target
    just under the drowning width leaves exactly the states that are too
    wide to search and too narrow to beam, which is a hole rather than a
    threshold -- so the beam runs whenever it can help at all.
    """
    start = _fold_norm(list(state))
    if len(start) <= target:
        return []
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


def _fold_plan(state: _FoldState) -> list[_FoldOp] | None:
    """Plan a full reduction, or ``None`` if the search gives up.

    A rotation pre-pass first wipes every unwiped group once (a bottom wipe
    at the minimum relocation lands above everything and preserves the
    cyclic order), because a group with extent cannot be a collision target
    and the search stalls while any remain.
    """
    st = _fold_norm(list(state))
    pre: list[_FoldOp] = []
    guard = 0
    while any(s > 0 for _, s, _, _ in st) and len(st) > 1:
        guard += 1
        if guard > 2 * len(state) + 4:
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
    wide = _fold_beam(st)
    if wide is None:
        wide = []
    cur: _FoldState | None = st
    for op in wide:
        assert cur is not None
        cur = _fold_apply(cur, op)
        if cur is None:  # pragma: no cover - replays a move the beam made
            return None
    assert cur is not None
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

    def __init__(self, truth_table: str, n: int) -> None:
        self.table = truth_table
        self.rows = 2**n
        self.pos: dict[_FoldKey, int] = {r: -_FOLD_STEP * r for r in range(self.rows)}
        self.cls: dict[_FoldKey, str] = {r: truth_table[r] for r in range(self.rows)}
        self.body: list[str] = []

    def _sub(self, k: int) -> str:
        code = _sub_code(k)
        assert code is not None, k
        return code

    def descend(self, k: int) -> None:
        if k == 0:
            return
        if k == 1:
            self.descend(3)
            self.plain_rise(2)
            return
        assert k >= 2
        assert all(v <= _LIMIT for v in self.pos.values())
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
        assert k >= 2
        assert all(-_LIMIT <= v <= _LIMIT for v in self.pos.values())
        assert all(v + k <= _LIMIT for v in self.pos.values())
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
        assert 2 * spread <= 2 * _LIMIT
        want_top = 1501
        if next_is_rise:
            # The next command sequence opens with ``p``, which wipes
            # anything below -3003, so the doubled state must fit both ways.
            want_top = max(spread - 1501, 0)
            assert want_top <= 1501, spread
        self.preshift(want_top - top)
        assert all(2 * v <= _LIMIT for v in self.pos.values())
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
        assert vic, vids
        assert got == vids, vids
        return vic

    def dive(self, c: int, vids: frozenset[int]) -> None:
        vic = self._vic(vids)
        assert len({self.cls[v] for v in vic}) == 1
        vt = max(self.pos[v] for v in vic)
        surv = [p for p in self.pos if p not in vic]
        q1 = (min(self.pos[p] for p in surv) - vt) if surv else 40
        assert _LIMIT + 1 <= c <= _LIMIT + q1, (c, q1)
        d = c + vt
        if d < 2:
            self.preshift(2 - d)
            d = c + max(self.pos[v] for v in vic)
        self.descend(d)
        below = {p for p, v in self.pos.items() if v < -_LIMIT}
        assert below == vic, (below, vic)
        self.body.append("pp")
        for p in vic:
            self.pos[p] = 0
        for p in self.pos:
            assert -_LIMIT <= self.pos[p] <= _LIMIT
        self._land(vic)

    def rise(self, c: int, vids: frozenset[int]) -> None:
        vic = self._vic(vids)
        assert len({self.cls[v] for v in vic}) == 1
        vb = min(self.pos[v] for v in vic)
        surv = [p for p in self.pos if p not in vic]
        q1 = (vb - max(self.pos[p] for p in surv)) if surv else 40
        assert _LIMIT + 1 <= c <= _LIMIT + q1, (c, q1)
        u = c - vb
        if u < 2:
            self.preshift(-(2 - u))
            u = c - min(self.pos[v] for v in vic)
        assert min(self.pos.values()) >= -_LIMIT
        assert all(self.pos[p] + u <= _LIMIT for p in surv)
        self.body.append("p" + self._sub(u) + "p")
        for p in self.pos:
            self.pos[p] += u
        over = {p for p, v in self.pos.items() if v > _LIMIT}
        assert over == vic, (over, vic)
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
            assert self.cls[o] == c, "cross-class landing"
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
                assert self.pos[lo] + u1 <= _LIMIT
                self.body.append("p" + self._sub(u1) + "ps")
                for p in self.pos:
                    self.pos[p] += u1
                assert self.pos[hi] > _LIMIT
                assert self.pos[lo] <= _LIMIT
                self.pos[hi] = 0
                for p in self.pos:
                    self.pos[p] -= 2
                pts = sorted(self.pos, key=lambda q: self.pos[q])
                lo, hi = pts
            gap = self.pos[hi] - self.pos[lo]
            assert gap >= 258, gap
            need = (-(self.byte(hi) - self.byte(lo)) - self.pos[lo]) % 256
            umin = max(_LIMIT + 1 - self.pos[hi], 2)
            umax = _LIMIT - self.pos[lo]
            u = next(
                (c0 for c0 in range(umin, umax + 1) if c0 % 256 == need),
                None,
            )
            assert u is not None, (umin, umax, need)
            self.body.append("p" + self._sub(u) + "ps")
            for p in self.pos:
                self.pos[p] += u
            assert self.pos[hi] > _LIMIT
            assert self.pos[lo] <= _LIMIT
            self.pos[hi] = 0
            for p in self.pos:
                self.pos[p] -= 2
            pts = sorted(self.pos, key=lambda q: self.pos[q])
            lo, hi = pts
            t = (self.byte(hi) - self.pos[hi]) % 256
            room = _LIMIT - self.pos[hi]
            while t > room:
                t -= 256
            self.preshift(t)
        for p in self.pos:
            assert self.pos[p] % 256 == self.byte(p) % 256, (
                self.pos[p],
                self.cls[p],
            )
            assert self.pos[p] <= _LIMIT
        self.body.append("e")


def _fold_setters(n: int) -> list[tuple[str, str]]:
    """One subtracting branch per input; ``pp`` holds at equal width."""
    out = []
    for i in range(n):
        width = _FOLD_STEP * 2 ** (n - 1 - i) // 2
        out.append(("pp" * (width // 2), "s" * width))
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
    6006 values a ``p`` can traverse, which holds through ``n == 10``.
    The search is exhaustive only below ~20 groups; wider states go
    through a beam first, so a plan is found in practice for every table
    tried (all of ``n <= 3``, large samples at 4 and 5, and the worst
    case, a fully alternating 32-run table) but is not proved total.
    """
    if _FOLD_STEP * (2**n - 1) > 2 * _LIMIT:
        return None
    runs: list[list[int]] = []
    for r in range(2**n):
        if runs and truth_table[runs[-1][-1]] == truth_table[r]:
            runs[-1].append(r)
        else:
            runs.append([r])
    state = [
        (
            -_FOLD_STEP * rn[0],
            _FOLD_STEP * (len(rn) - 1),
            truth_table[rn[0]],
            frozenset(rn),
        )
        for rn in runs
    ]
    ops = _fold_plan(_fold_norm(state))
    if ops is None:
        return None
    emitter = _FoldEmitter(truth_table, n)
    for idx, (kind, _, c, vids) in enumerate(ops):
        if kind == "m":
            emitter.double(next_is_rise=(idx + 1 < len(ops) and ops[idx + 1][0] == "u"))
        elif kind == "d":
            emitter.dive(c, vids)
        else:
            emitter.rise(c, vids)
    emitter.finish()
    header = ";".join(
        f"{k}={zero}|{one}" for k, (zero, one) in enumerate(_fold_setters(n))
    )
    placeholders = "".join("{X" + str(k) + "}" for k in range(n))
    return header + _HEADER_END + placeholders + "".join(emitter.body)


def _affine(truth_table: str, n: int) -> str | None:
    """Build a composed-affine template, or ``None`` if the table is not one.

    This is the wide construction above two inputs.  The two-input derivation
    reads one slope per column and does not generalise; the cascade builds only
    subcubes.  Composing one affine setter per input reaches neither's limit:
    it builds 84 of the 256 three-input tables, XOR and XNOR among them, which
    no subcube is.

    The 84 is measured and stable -- widening the multipliers, the offsets, the
    spelling depth and the witness count each reach no further table -- but it
    is *not* known to be a maximum.  The shared-cofactor law admits 88, and it
    is tempting to read that as the ceiling; it is not one, because the law
    constrains the last input alone.  Measured against it, this path reaches 32
    tables the law does not admit and misses 36 that it does, so the two sets
    cross rather than nest.  What the path does not reach is an OR of several
    disjoint subcubes, majority-3 being the smallest.  That was recorded here
    as a limit of the *model* -- chaining indicator gadgets was said to need a
    running total to survive a gadget that erases, and there is one register --
    but the argument does not bind: :func:`_ladder` keeps the running total in
    the accumulator itself and lets the over-3003 reset read it as a threshold,
    which builds majority-3.  What is true is narrower, that no composition of
    *affine* setters reaches it.  See ``docs/limitations.md``.
    """
    found = _affine_tables(n).get(truth_table)
    if found is None:
        return None
    setters, tail = found
    header = ";".join(f"{k}={zero}|{one}" for k, (zero, one) in enumerate(setters))
    body = "".join("{X" + str(k) + "}" for k in range(n)) + tail
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
        # Reaching this raise means the fold's plan search gave up, which no
        # tested table does -- all of n <= 3, large executed samples at four
        # and five inputs, and the fully alternating worst case all plan.
        # The guard stays because emitting nothing is better than emitting a
        # program that computes the wrong function.
        if fold is None:  # pragma: no cover - no known table reaches this
            raise ValueError(
                f"%^2^-1 builds every table at one, two, three and four "
                f"inputs, and every five-input table tried; beyond those a "
                f"conjunction or disjunction of literals at any arity, the "
                f"thresholds a weighted ladder crosses, the tables a deep "
                f"band schedules, and the tables the fold can plan -- which "
                f"needs the row ladder to fit the workspace (n <= 10) and "
                f"the plan search to close; "
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
