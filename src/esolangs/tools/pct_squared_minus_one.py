r"""Build parameterized Boolean programs for %^2^-1.

Programs that read their own inputs cannot compute a two-input function, so
this module embeds each input once and uses affine setters, threshold ladders,
and relocation folds. Every construction is derived and replayed on all
instantiated rows.
"""

from functools import cache

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.helpers import _validate_truth_table, instantiate
from esolangs.tools.pct_codes import (
    _DECL_RE,
    _HEADER_END,
    _affine_code,
    _pad_pair,
    _sub_code,
    _tail_for,
)

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach
# it by this name.  Re-exported in the ``x as x`` form so a caller that
# does not care where a piece lives need not know.
from esolangs.tools.pct_codes import (
    _LIMIT as _LIMIT,
)
from esolangs.tools.pct_codes import (
    _apply as _apply,
)
from esolangs.tools.pct_codes import (
    _even_width_for as _even_width_for,
)
from esolangs.tools.pct_codes import (
    _sub_of_width as _sub_of_width,
)
from esolangs.tools.pct_deep import (
    _BAND_UNIT as _BAND_UNIT,
)
from esolangs.tools.pct_deep import (
    _deep_band,
)
from esolangs.tools.pct_deep import (
    _deep_plan as _deep_plan,
)
from esolangs.tools.pct_deep import (
    _deep_values as _deep_values,
)
from esolangs.tools.pct_deep import (
    _deep_weightings as _deep_weightings,
)
from esolangs.tools.pct_fold import (
    _centred_setter as _centred_setter,
)
from esolangs.tools.pct_fold import (
    _fold,
    _interleaved_fold,
)
from esolangs.tools.pct_fold import (
    _fold_positions as _fold_positions,
)
from esolangs.tools.pct_fold import (
    _fold_setters as _fold_setters,
)
from esolangs.tools.pct_fold import (
    _fold_span as _fold_span,
)
from esolangs.tools.pct_fold import (
    _fold_subset_weights as _fold_subset_weights,
)
from esolangs.tools.pct_fold import (
    _fold_to_cofactors as _fold_to_cofactors,
)
from esolangs.tools.pct_fold import (
    _fold_uniform as _fold_uniform,
)
from esolangs.tools.pct_fold import (
    _FoldEmitter as _FoldEmitter,
)
from esolangs.tools.pct_fold import (
    _interleaved_final_pair as _interleaved_final_pair,
)
from esolangs.tools.pct_fold import (
    _split_setter as _split_setter,
)
from esolangs.tools.pct_fold_plan import (
    _COFACTOR_BRIDGE_POINTS as _COFACTOR_BRIDGE_POINTS,
)
from esolangs.tools.pct_fold_plan import (
    _FOLD_NARROW_STEP as _FOLD_NARROW_STEP,
)
from esolangs.tools.pct_fold_plan import (
    _FOLD_STEP as _FOLD_STEP,
)
from esolangs.tools.pct_fold_plan import (
    _cofactor_done as _cofactor_done,
)
from esolangs.tools.pct_fold_plan import (
    _fold_clean_amount as _fold_clean_amount,
)
from esolangs.tools.pct_fold_plan import (
    _fold_construct as _fold_construct,
)
from esolangs.tools.pct_fold_plan import (
    _fold_done as _fold_done,
)
from esolangs.tools.pct_fold_plan import (
    _fold_geometry as _fold_geometry,
)
from esolangs.tools.pct_fold_plan import (
    _fold_merge as _fold_merge,
)
from esolangs.tools.pct_fold_plan import (
    _fold_moves as _fold_moves,
)
from esolangs.tools.pct_fold_plan import (
    _fold_norm as _fold_norm,
)
from esolangs.tools.pct_fold_plan import (
    _fold_plan as _fold_plan,
)
from esolangs.tools.pct_fold_plan import (
    _fold_reduce as _fold_reduce,
)
from esolangs.tools.pct_fold_plan import (
    _fold_resolve as _fold_resolve,
)
from esolangs.tools.pct_fold_plan import (
    _fold_rule_move as _fold_rule_move,
)
from esolangs.tools.pct_fold_plan import (
    _fold_served as _fold_served,
)
from esolangs.tools.pct_fold_plan import (
    _fold_skeleton as _fold_skeleton,
)
from esolangs.tools.pct_fold_plan import (
    _fold_step as _fold_step,
)
from esolangs.tools.pct_ladder import (
    _LADDER_GADGETS as _LADDER_GADGETS,
)
from esolangs.tools.pct_ladder import (
    _LADDERS as _LADDERS,
)
from esolangs.tools.pct_ladder import (
    _ladder,
)
from esolangs.tools.pct_ladder import (
    _ladder_built as _ladder_built,
)
from esolangs.tools.pct_ladder import (
    _ladder_gadget as _ladder_gadget,
)
from esolangs.tools.pct_ladder import (
    _ladder_setters as _ladder_setters,
)
from esolangs.tools.pct_ladder import (
    _ladder_vector as _ladder_vector,
)
from esolangs.tools.pct_ladder import (
    _sub_units as _sub_units,
)

__all__ = ["pct_squared_minus_one"]


#: Affine multipliers a setter may realise: identity, negate, erase, double.
_A_VALS = (1, -1, 0, 2)


#: Offsets considered for a setter branch.  The derived solutions never need a
#: magnitude past 8 (XOR's ``+/-8`` is the extreme), so this window is a
#: statement about the construction rather than a search budget.
_OFFSETS = range(-10, 11)


#: Accumulator values the answers ``(0, 1)`` may land on before the tail runs.
#: The tail has to move these onto ``0``/``1``, and :func:`_tail_for` does that
#: with one translation, which needs the pair a step apart -- so nearby pairs
#: are the only pairs that print.
_CLASS_PAIRS = tuple(
    (zero, one) for zero in range(-9, 10) for one in range(-9, 10) if zero != one
)


#: The class pairs that actually print, which is 32 of the 342 in
#: :data:`_CLASS_PAIRS`.  A tail is a bare translation, optionally after a
#: ``p``, so it exists only when the pair is one step apart in one direction or
#: the other -- and even then not always, because ``_sub_code`` has no spelling
#: for a shift of 1, which is what strikes ``(1, 0)``, ``(1, 2)``, ``(-1, 0)``
#: and ``(-1, -2)`` out of the survivors.
#:
#: This is a *filter on dead iterations*, not a change of search space.
#: :func:`_solution` ends with ``_tail_for(classes[1], classes[0])`` and returns
#: ``None`` when it misses, so a pair outside this tuple can never reach
#: :func:`_derive`'s ``best``, whatever the rest of the parameter set is.  The
#: comprehension preserves ``_CLASS_PAIRS`` order and ``best`` keeps the first
#: candidate of a given width, so the winner is unchanged as well as the reach.
#: Skipping the other 310 is worth 8.6x on the call count -- measured at
#: 619k :func:`_solution` calls per two-input table against 72k -- and 6.1x
#: end to end on the eighteen-table profile that found this loop (2.28s to
#: 0.37s).  The remaining time is the same nest at a tenth the width, so
#: hoisting inside it was measured and left out: it is worth about 0.1s.
_VIABLE_CLASS_PAIRS = tuple(
    pair for pair in _CLASS_PAIRS if _tail_for(pair[1], pair[0]) is not None
)


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

    The class values come from :data:`_VIABLE_CLASS_PAIRS` rather than the
    full grid, because a pair the tail cannot print rejects every parameter
    set it appears in -- see that tuple for why the filter cannot move the
    winner.
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
                        for classes in _VIABLE_CLASS_PAIRS:
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


#: Multipliers the wide search composes: the closure of ``m`` (double) and
#: ``p`` (negate) over the identity, bounded by ``_WIDE_A_LIMIT``, then the
#: erase.  So ``mp`` is ``-2``, ``mm`` is ``4`` and ``mmp`` is ``-4``.
#:
#: Written as the closure rather than as the seven values it comes to,
#: because the bound is the only measured part: widening past ``|a| == 4``
#: reaches no further table, while the *shape* -- signed powers of two --
#: is what the two commands generate and is not a search result.  Order is
#: required because the wide search takes the first spelling that
#: behaves: ascending magnitude, positive before negative.
_WIDE_A_LIMIT = 4


def _wide_a_vals(limit: int) -> tuple[int, ...]:
    """Return the reachable multipliers up to ``limit``, in search order."""
    powers = []
    value = 1
    while value <= limit:
        powers.append(value)
        value *= 2
    return (0, *(signed for p in powers for signed in (p, -p)))


_WIDE_A_VALS = _wide_a_vals(_WIDE_A_LIMIT)

#: Offsets the wide search composes.  Measured: widening to ``+/-16`` reaches
#: no table that ``+/-12`` misses.
_WIDE_B_VALS = tuple(range(-12, 13))

#: Window the derived spellings are checked against in tests.
_SPELL_WINDOW = range(-90, 91)

#: Longest derived command string used for one branch.
_SPELL_MAX = 18

#: Odd-width identity: subtract six, negate, subtract six, negate.
_ODD_AFFINE_IDENTITY = "ssspiip"


_WIDE_A_CODE = {0: "'", 1: "", -1: "p", 2: "m", -2: "mp", 4: "mm", -4: "mmp"}


def _wide_affine_code(a: int, b: int) -> str:
    """Spell one map in the shipped affine grid directly."""
    if b == -1:
        offset = "ipsp"
    elif b == 1:
        offset = "spip"
    elif b == 0:
        offset = ""
    else:
        sub = _sub_code(abs(b))
        if sub is None:  # pragma: no cover - the grid excludes other gaps
            raise AssertionError(b)
        offset = sub if b < 0 else f"p{sub}p"
    return _WIDE_A_CODE[a] + offset


@cache
def _spell_bases() -> dict[tuple[int, int], tuple[str | None, str | None]]:
    """Return directly derived bases for each grid map and width parity."""
    bases: dict[tuple[int, int], tuple[str | None, str | None]] = {}
    for a in _WIDE_A_VALS:
        for b in _WIDE_B_VALS:
            base = _wide_affine_code(a, b)
            if a == 0:
                bases[a, b] = (base, None)
            else:
                by_parity: list[str | None] = [None, None]
                by_parity[len(base) % 2] = base
                other = base + _ODD_AFFINE_IDENTITY
                by_parity[len(other) % 2] = other
                bases[a, b] = (by_parity[0], by_parity[1])
    return bases


def _spellings_by_width(a: int, b: int) -> dict[int, str]:
    """Map width to a command string realising ``x -> a*x + b`` at that width.

    :func:`_affine_code` gives one spelling per map, which fixes its width.
    That is what makes an odd width gap between a setter's two branches
    unfixable: :func:`_pad_pair` pads with ``pp`` and closes only even gaps.
    Each nonconstant map has directly derived bases of both parities, so a pair
    whose natural widths differ by one can be respelled to a common width.

    Derived from :func:`_spell_bases` by padding rather than enumerated: a
    base plus ``pp`` repeated reaches every width of its parity, and an
    ``a == 0`` base takes an ``s`` prefix per extra width.
    """
    found = _spell_bases().get((a, b))
    if found is None:  # pragma: no cover - every grid map has a base
        return {}
    out: dict[int, str] = {}
    even, odd = found
    if a == 0:
        base = even if even is not None else odd
        if base is None:
            raise AssertionError("base is not None")
        for width in range(len(base), _SPELL_MAX + 1):
            out[width] = "s" * (width - len(base)) + base
        return out
    for base in (even, odd):
        if base is None:  # pragma: no cover - only a == 0 maps miss a parity
            # All 25 single-parity maps in the grid have ``a == 0``, and those
            # returned above, so both bases exist by the time the loop runs.
            # The guard stays because it is what makes that reasoning local:
            # a future base table with a one-parity ``a != 0`` map would skip
            # it here rather than pad a ``None``.
            continue
        for width in range(len(base), _SPELL_MAX + 1, 2):
            out[width] = base + "pp" * ((width - len(base)) // 2)
    return out


#: One branch of a setter as an affine map, ``(a, b)`` for ``x -> a*x + b``.
_Branch = tuple[int, int]


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
        # The cascade covers every subcube at any arity, and is usually the
        # shorter -- ``2n + 4`` characters against the affine path's setters.
        # *Usually* is not always, so at three inputs, where both are cheap,
        # the two are built and the shorter kept: returning the cascade on
        # sight served 44 of 256 tables a longer program than the affine
        # path gives, by up to 7 characters (``00000101`` is 40 against 33).
        # Building both over that corpus costs 0.466s against 0.590s for
        # returning early, since a served cascade skips no work the affine
        # path would have done -- the comparison is free here.
        cascade = _cascade(truth_table, n)
        # Tables that are not subcubes may still compose from one affine
        # setter per input, which is what reaches XOR at three inputs.
        #
        # Only at three.  This path derives a whole arity at once and its
        # composition frontier grows 90 -> 1630 -> 36458 states at n = 2, 3, 4,
        # so a four-input table costs about two minutes here whether or not it
        # ends up served -- parity-4 was measured at 125s, against 0.01s for the
        # deep band that serves it instead.  The deep band covers every table
        # this path reaches above three inputs, so the enumeration is skipped
        # rather than paid for; at three inputs it stays, where it is instant.
        affine = _affine(truth_table, n) if n == 3 else None
        # Ties keep the cascade, which is what the order emitted before.
        best = min(
            (build for build in (cascade, affine) if build is not None),
            key=len,
            default=None,
        )
        if best is not None:
            return best
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
            raise GeneratorCapError(
                f"%^2^-1 builds every table at one, two, three and four "
                f"inputs, and every table tried from five through thirteen; "
                f"beyond those a conjunction or disjunction of literals at "
                f"any arity, the thresholds a weighted ladder crosses, the "
                f"tables a deep band schedules, the tables the all-row fold "
                f"can plan, and the compactable suffix-cofactor stages the "
                f"interleaved fold can plan; "
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

    The header's own newlines are discarded before it is read, which is what
    lets the wrapper fold a header at all -- and lets it fold *inside* a
    declaration rather than only between two, which matters because a single
    declaration is 175 characters and does not shrink with ``n``.  Stripping
    here rather than substituting the rows as they come keeps the filled
    program byte-identical however the header was folded, so the two
    branches stay equal width in text as well as in commands.
    """
    header, _, body = template.partition(_HEADER_END)
    header = header.replace("\n", "")
    branches = {
        int(m.group(1)): (m.group(2), m.group(3)) for m in _DECL_RE.finditer(header)
    }
    return instantiate(body, bits, lambda index, bit: branches[index][bit])
