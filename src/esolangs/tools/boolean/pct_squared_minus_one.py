r"""Build parameterized Boolean programs for %^2^-1.

Programs that read their own inputs cannot compute a two-input function, so
this module embeds each input once and uses affine setters, threshold ladders,
and relocation folds. Every construction is derived and replayed on all
instantiated rows.
"""

import re
from collections.abc import Callable, Iterator
from functools import cache
from itertools import chain, pairwise

from esolangs.exceptions import GeneratorCapError
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
#: are the only pairs that print.
_CLASS_PAIRS = tuple(
    (zero, one) for zero in range(-9, 10) for one in range(-9, 10) if zero != one
)

#: Separates the setter header from the program body in a template.
#:
#: A *blank line*, not a newline, so that the header may be folded across
#: rows like the body: a single newline is then interior to whichever of the
#: two it falls in, and only the blank line divides them.  Nothing emits a
#: blank line inside either part -- the wrapper's packing never produces an
#: empty row -- so the division is unambiguous.
#:
#: This is a template-format constant, not a language one.  The interpreter
#: never sees a header; :func:`fill` consumes it.
_HEADER_END = "\n\n"

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

#: Window a candidate spelling is checked against.  A spelling is admitted
#: because it *behaves* as ``a*x + b`` here, not because it matches a template,
#: which is what lets ``mp`` be found as ``a == -2`` without a rule for it.
_SPELL_WINDOW = range(-90, 91)

#: Longest command string the speller enumerates for one branch.
_SPELL_MAX = 7


#: The alphabet a branch spells its map in: erase, step, double, negate.
_SPELL_ALPHABET = "simp'"


def _spell_map(window: tuple[int, ...]) -> tuple[int, int] | None:
    """Return ``(a, b)`` if ``window`` is ``a*x + b`` throughout, else ``None``.

    The window carries what a command string leaves for each input in
    :data:`_SPELL_WINDOW`, so a spelling is admitted because it *behaves*
    affinely here, not because it matches a template -- which is what lets
    ``mp`` be found as ``a == -2`` with no rule written for it.
    """
    first, second = window[0], window[1]
    a = second - first
    b = first - a * _SPELL_WINDOW[0]
    pairs = zip(_SPELL_WINDOW, window, strict=True)
    if any(value != a * x + b for x, value in pairs):
        return None
    return a, b


@cache
def _spell_bases() -> dict[tuple[int, int], tuple[str | None, str | None]]:
    """Minimal spelling of each grid map, per width parity.

    ``(a, b)`` maps to ``(shortest even-width spelling, shortest odd-width
    spelling)``, either ``None`` where that parity has no spelling within
    :data:`_SPELL_MAX`.  For ``a == 0`` the erase kills everything before
    it, so one base spells every width above its own and the second slot is
    always ``None``.

    Built rather than stored.  Command strings are grown a character at a
    time and carried as the window they leave -- the whole point of
    :func:`_spell_map` -- so two strings that act alike are one state and
    the growth stays flat instead of branching five ways per character.
    The first string to reach a map at a parity is its minimal spelling,
    since strings are grown shortest first.

    Everything beyond these bases is derivable, which is why only they are
    built: appending ``pp`` -- two negations, an identity the interpreter
    executes -- widens any spelling by two without changing its map, and an
    ``a == 0`` base takes an ``s`` prefix per extra width.  A map's width
    set is exactly the arithmetic progressions its bases seed, which
    :func:`_spellings_by_width` rebuilds below.
    """
    window = tuple(_SPELL_WINDOW)
    shortest: dict[tuple[tuple[int, int], int], str] = {}
    # The empty string is the identity map, and it is even-width.
    identity = _spell_map(window)
    # The window is x itself.
    if identity is None:
        raise AssertionError("identity is not None")
    shortest[identity, 0] = ""
    frontier = {window: ""}
    for length in range(1, _SPELL_MAX + 1):
        grown: dict[tuple[int, ...], str] = {}
        for carried, code in frontier.items():
            for char in _SPELL_ALPHABET:
                moved = tuple(_apply(value, char) for value in carried)
                if moved not in grown:
                    grown[moved] = code + char
        frontier = grown
        for carried, code in frontier.items():
            spelled = _spell_map(carried)
            if spelled is None:
                continue
            key = (spelled, length % 2)
            if key not in shortest:
                shortest[key] = code
    bases: dict[tuple[int, int], tuple[str | None, str | None]] = {}
    for a in _WIDE_A_VALS:
        for b in _WIDE_B_VALS:
            even = shortest.get(((a, b), 0))
            odd = shortest.get(((a, b), 1))
            if a == 0:
                # The erase forgets the prefix, so the shorter base spells
                # every width above its own and the odd slot stays empty.
                found = [code for code in (even, odd) if code is not None]
                # Every grid map spells.
                if not found:
                    raise AssertionError((a, b))
                bases[a, b] = (min(found, key=len), None)
            else:
                # As above.
                if not (even or odd):
                    raise AssertionError((a, b))
                bases[a, b] = (even, odd)
    return bases


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

    Derived from :func:`_spell_bases` by padding rather than enumerated: a
    base plus ``pp`` repeated reaches every width of its parity, and an
    ``a == 0`` base takes an ``s`` prefix per extra width.  The width *sets*
    are therefore identical to the enumeration's -- checked exhaustively
    over the grid before the enumeration was retired -- so which tables
    build, and at what width, is unchanged; only the characters inside a
    wider-than-minimal branch differ, and those are re-executed like
    everything else.
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


#: Ladders the search runs, as ``(weights, base)``.  Every value is a multiple
#: of 250 and every rung stays within ``[-3003, 0]``, which is what keeps stage
#: one exactly affine: the reset fires only above 3003 and never on a negative
#: accumulator, so no rung clamps before the suffix asks it to.
#:
#: These eight are a *cover*, not a grid.  The full product of four weights and
#: four bases leaves 256 distinct ladders, of which 150 reach some table the
#: other paths miss; greedy set cover over their yields picks these eight, which
#: between them reach all twenty.
#:
#: The cover is minimal -- dropping any one of the eight strands tables (four
#: for the first three, two for the rest) -- and it determines *size*:
#: removing the ladder path entirely costs no correctness but 88% more
#: characters over the twenty it serves (31615 against 59457), with
#: majority-of-three going 874 to 2280.
#:
#: **What keeping eight rather than all 256 buys is assignment stability, not
#: build time.**  An earlier revision of this comment priced the full grid at
#: about fifty seconds; measured, folding all 256 takes **0.21s** against the
#: cover's 0.01s.  What the full grid does change is reach -- 50 tables against
#: 26 -- and every one of those 24 extras already builds by an earlier path, so
#: widening would only move which path claims them.  That is a behaviour
#: change, which is the reason the cover ships, and it is the same argument
#: :data:`_LADDER_CUTS` makes.
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

    The arithmetic and the emitted characters have to agree, and modelling
    them separately is what let an earlier version claim a program the
    interpreter then contradicted: a hold negates, and a magnitude past the
    limit clamps to zero on the very next command.  Running :func:`_apply`
    over the code actually emitted removes that whole class of divergence.
    """
    out = []
    for index in range(2**n):
        code = lead
        for position, (zero, one) in enumerate(setters):
            code += one if (index >> (n - 1 - position)) & 1 else zero
        out.append(_apply(0, code))
    return tuple(out)


#: The five comparators the ladder path composes after stage one, as
#: ``(cut, slope)`` -- the two numbers a gadget is a function of, with
#: :func:`_ladder_gadget` spelling each one.  ``cut`` is the outer
#: threshold on the rung's magnitude and ``slope`` is the total scale the
#: second stage reaches, which fixes the inner threshold at
#: ``ceil(3004 / slope)``; between them a gadget sends rungs at or past
#: the cut (plus rung 0, when the offsets allow it) to one class and the
#: band between the thresholds to the other.  These pairs are a measured
#: cover with the same status as :data:`_LADDERS`: which comparators the
#: twenty tables need was found by search, and what ships is its result.
#: The spellings themselves are constructed -- an earlier comment here
#: claimed deriving them meant re-running the rung composition, but the
#: composition is forced (see :func:`_ladder_gadget`), and the frozen
#: strings now live in the suite as the fixture the rule must reproduce.
#:
#: Five pairs suffice for the same reason eight ladders do: enumerating
#: every comparator the grammar spells -- one per outer 250-band each
#: slope reaches, 83 gadgets in all -- and folding them over the ladders
#: serves nothing these five miss.  It picks up ten tables the shipped
#: fold never lists, but every one already builds through an earlier path,
#: and four would flip from the deep band or the fold to a ladder program,
#: so the wider family buys behaviour change rather than reach.
_LADDER_CUTS = ((3004, 4), (1502, 4), (1500, 4), (751, 8), (3004, 8))


def _sub_units(units: int) -> str:
    """Shortest ``s``/``i`` spelling of a subtraction of ``units``.

    ``s`` takes 2 and ``i`` takes 3, so the shortest spelling packs as
    many ``i`` as the remainder mod 3 allows; a remainder of 1 borrows
    one ``i`` back to pay it as two ``s`` (so 1 unit alone is
    unspellable, which no caller asks for).
    """
    # Unspellable; silence would emit "ss".
    if units == 1:
        raise AssertionError("units != 1")
    if units % 3 == 0:
        return "i" * (units // 3)
    if units % 3 == 2:
        return "i" * (units // 3) + "s"
    return "i" * (units // 3 - 1) + "ss"


def _ladder_gadget(cut: int, slope: int) -> str:
    """Spell the comparator with outer threshold ``cut`` and scale ``slope``.

    Every gadget is ``PRE + "psp" + MID + "ipsp"``, and both halves are
    arithmetic, not composition:

    * ``PRE`` is ``"s" * k + "m" * j``, mapping a rung ``v <= 0`` to
      magnitude ``2**j * (|v| + 2k)``; the ``p`` that follows turns it
      positive, so the reset ahead of the next command fires exactly when
      ``|v| >= ceil(3004 / 2**j) - 2k == cut``.  ``j`` is the largest
      power fitting under the cut, ``k`` pays the even remainder.
    * ``MID`` doubles ``slope // 2**j`` times.  Its subtractions are not
      free: the class that survived the first reset must land on 2 and a
      rung at 0 must land on 3 (one step past it), so the deficit is
      pinned at ``max(0, 2*m - m*b - 4)`` where ``b`` is ``PRE``'s
      additive part.  A ``PRE`` whose ``b`` pushes that negative cannot
      normalise rung 0 -- the ``(1500, 4)`` gadget, whose ladders never
      stand a rung there.  The deficit is spelled in the highest-weight
      gap first, each gap's characters doubled by the ``m`` still to run.

    The five shipped pairs come out byte-identical to the strings the
    search found (``test_ladder_gadgets_match_frozen_spellings``), so
    this is the same catalogue, constructed.
    """
    j = (3004 // cut).bit_length() - 1
    remainder = -(-3004 // (1 << j)) - cut
    if remainder < 0 or remainder % 2:
        j -= 1
        remainder = -(-3004 // (1 << j)) - cut
    if j < 0:
        raise AssertionError("j >= 0")
    if remainder < 0:
        raise AssertionError("remainder >= 0")
    if remainder % 2 != 0:
        raise AssertionError("remainder % 2 == 0")
    k = remainder // 2
    pre = "s" * k + "m" * j
    offset = 2 * k * (1 << j)
    doublings = slope // (1 << j)
    if doublings * (1 << j) != slope:
        raise AssertionError("doublings * (1 << j) == slope")
    if doublings < 2:
        raise AssertionError("doublings >= 2")
    deficit = max(0, 2 * doublings - doublings * offset - 4)
    mid = ""
    for gap in range(doublings.bit_length() - 1):
        weight = 1 << (doublings.bit_length() - 2 - gap)
        units = deficit // weight
        mid += "m" + _sub_units(units)
        deficit -= units * weight
    if deficit != 0:
        raise AssertionError("deficit == 0")
    return pre + "psp" + mid + "ipsp"


_LADDER_GADGETS = tuple(_ladder_gadget(cut, slope) for cut, slope in _LADDER_CUTS)

#: How a gadget finishes: ``sl`` prints the split as it stands, ``ipl``
#: inverts it first, so the pair covers a table and its complement.
_LADDER_TAILS = ("sl", "ipl")


@cache
def _ladder_built() -> dict[str, tuple[int, str]]:
    """Every table the ladder path serves: table to ``(ladder, suffix)``.

    Built rather than stored.  Stage one leaves each input combination on a
    rung of :data:`_LADDERS`, and a suffix is a comparator that splits those
    rungs into the two output classes -- so running the suffix over the
    stage-one vector *computes* the table it serves, and folding every
    (suffix, ladder) pair the other way round names them all.

    The fold is forward and first-claim-wins, never a search for a target:
    suffixes shortest first, ladders in :data:`_LADDERS` order, which is what
    the docstring of that cover means by "the first ladder whose stage-one
    vector the suffix splits".  The arithmetic is :func:`_apply` over the
    characters actually emitted, not a model of them -- see
    :func:`_ladder_vector` for why anything else drifts.

    A pair whose rungs do not all land on 0 or 1 is not a split and is
    skipped.  Two of the tables reached here are the constants, which every
    earlier path serves in a tenth the characters, so naming them costs
    nothing: :func:`_ladder` is tried last.
    """
    built: dict[str, tuple[int, str]] = {}
    vectors = []
    for weights, base in _LADDERS:
        spelled = _ladder_setters(weights, base)
        # The cover spells.
        if spelled is None:
            raise AssertionError(weights)
        setters, lead = spelled
        vectors.append(_ladder_vector(setters, lead, 3))
    for gadget in _LADDER_GADGETS:
        for tail in _LADDER_TAILS:
            suffix = gadget + tail
            for index, vector in enumerate(vectors):
                rungs = [_apply(rung, suffix) for rung in vector]
                if any(rung not in (0, 1) for rung in rungs):
                    continue
                built.setdefault("".join(str(rung) for rung in rungs), (index, suffix))
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
    if n != 3:
        # Every shipped ladder has three weights, so the harvest this
        # tabulation froze was empty at every other arity.
        return None
    found = _ladder_built().get(truth_table)
    if found is None:
        return None
    index, suffix = found
    weights, base = _LADDERS[index]
    spelled = _ladder_setters(weights, base)
    # Every shipped weight spells.
    if spelled is None:
        raise AssertionError(index)
    setters, lead = spelled
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
    branches swap -- and it is what frees the order.
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
        # The first prefix that spells a drop spells a body too, so the
        # loop always returns on that pass rather than trying another.
        if body is not None:  # pragma: no branch
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
    # Rows collapse onto their runs' values -- eleven for parity-10, never
    # more than the span budget allows -- so each code runs once per value,
    # not once per row.
    moved = {-v: _apply(-v, dropped + "p") for v in set(values)}
    current = {r: moved[-values[r]] for r in rows}
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
        lifted = {v: _apply(v, raise_code + "s") for v in set(current.values())}
        raised = {r: lifted[v] for r, v in current.items()}
        down = _DEEP_PARK - max(raised.values())
        park = _affine_code(1, down)
        if park is None:
            return None  # pragma: no cover - screened by legality
        lowered = {v: _apply(v, park) for v in set(raised.values())}
        parked = {r: lowered[v] for r, v in raised.items()}
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
        shifted = {v: _apply(v, tail) for v in set(current.values())}
        printed = {r: shifted[v] for r, v in current.items()}
        # A band reaching here has a working shift among the seventeen, so
        # the first spellable tail prints and the loop returns.
        if all(  # pragma: no branch
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
    # A diff is the disjoint bit pair ``(plus, minus)`` -- where the first
    # row has a 1 the second lacks, and vice versa -- so pairs dedup as one
    # packed int each and only the distinct survivors spell out as tuples.
    # ``lead > 0`` says the top differing bit is a plus, i.e. ``plus > minus``.
    seen: set[int] = set()
    size = 2**n
    for row in range(size):
        for other in range(row + 1, size):
            if truth_table[row] == truth_table[other]:
                continue
            # ``other > row``, so the highest bit the two differ on is
            # always other's: ``other & ~row`` therefore always exceeds
            # ``row & ~other``, and the canonical order is the swap every
            # time rather than a comparison.
            plus, minus = other & ~row, row & ~other
            seen.add((plus << n) | minus)
    diffs = []
    for key in seen:
        plus, minus = key >> n, key & (size - 1)
        diffs.append(
            tuple(
                ((plus >> (n - 1 - k)) & 1) - ((minus >> (n - 1 - k)) & 1)
                for k in range(n)
            )
        )
    return sorted(diffs)


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

    The enumeration backtracks on the remaining sum budget rather than
    filtering ``(cap + 1) ** n`` products -- 282M walked tuples at ten
    inputs against the 343K that survive -- and the sort key is a total
    order, so generation order cannot show through: same set, same tuple.
    """
    budget = _LIMIT // _BAND_UNIT
    units = [0] * n
    by_sum: list[list[tuple[int, ...]]] = [[] for _ in range(budget + 1)]

    def fill(index: int, left: int) -> None:
        for unit in range(min(_DEEP_CAP, left) + 1):
            units[index] = unit
            if index + 1 == n:
                by_sum[budget - left + unit].append(tuple(units))
            else:
                fill(index + 1, left - unit)
        units[index] = 0

    fill(0, budget)
    by_sum[0].clear()  # the all-zero tuple, the one sum-0 composition
    for bucket in by_sum:
        bucket.sort(key=lambda u: (max(u), u))
    return tuple(chain.from_iterable(by_sum))


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
    8 random five-input tables build -- about 18 seconds each to prove on
    the old product enumeration, about 60ms now that zero-unit weightings
    skip -- while parity-5 and majority-5 build in 0.14s.  The check stays
    either way: what builds is part of the contract, and the screen is
    what pins it to the symmetric tables rather than to whatever shorter
    program the enumeration occasionally finds.
    """
    if n > _LIMIT // _BAND_UNIT:
        # Each unit prices a whole residue system, so even the all-ones
        # weighting costs ``n * 256`` of span and the budget tops out at
        # eleven inputs.  A zero unit cannot rescue a table here either:
        # only symmetric tables pass the screen below, and a symmetric
        # table that ignores an input is constant -- which the cascade
        # already served.  Refusing up front skips the sum-bounded
        # enumeration below -- a million-tuple walk at thirteen inputs
        # whose every survivor the zero-unit argument rejects.
        return None
    if n > 4 and any(
        len({truth_table[r] for r in range(2**n) if bin(r).count("1") == pop}) > 1
        for pop in range(n + 1)
    ):
        return None
    diffs = _cross_class_diffs(truth_table, n)
    # A singleton diff -- rows apart in one coordinate -- totals
    # ``±units[k]`` under every mask, so a weighting with a zero unit
    # there is illegal at all masks and can be skipped without testing
    # any.  Every non-constant symmetric table has all ``n`` singletons
    # (any coordinate can carry a class-boundary bit flip), and that is
    # everything past the screen above, so past four inputs the skip is
    # the C-speed ``0 in units``.  Parity is the extreme case again: all
    # 24219 weightings ordered before the popcount ladder at nine inputs
    # have a zero unit, so the ladder is the first weighting *tested*.
    singles = {diff.index(1) for diff in diffs if sum(map(abs, diff)) == 1}
    full_screen = len(singles) == n
    for units in _deep_weightings(n):
        if full_screen:
            if 0 in units:
                continue
        elif any(not units[k] for k in singles):
            continue
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
#: It is a *fallback* rather than the default because every shipped program
#: is built on the wider ladder: at four inputs and below the narrow ladder
#: plans the same tables but emits different characters, so trying it only
#: on a miss keeps every template that builds today byte-identical and
#: confines the change to the arities that refused.
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
#: 12``) top out at four.  Above this a doomed arity used to get expensive --
#: a 512-point state burned the retired best-first bridge's 50000-state cap
#: for 192s -- while contributing no build, so it is declined instead of
#: paid for.
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
            # The span check above is the merge's own precondition, so a
            # pair that passes it always merges.
            if merged is not None:  # pragma: no branch
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


def _fold_wipe_frame(
    state: _FoldState, kind: str, k: int
) -> tuple[int, list[tuple[int, int, str]]] | None:
    """Return ``(q1, survivor tops)`` for a wipe, or ``None`` if it is illegal.

    The same window arithmetic :func:`_fold_moves` uses -- ``q1`` is the gap
    from the victims to the nearest survivor, and each survivor's top is
    given as its distance from the victims' reference edge -- computed
    directly so a single named move can be checked without enumerating every
    move the state offers.
    """
    ordered = sorted(state, key=lambda t: t[0] if kind == "d" else -t[0])
    vic, surv = ordered[:k], ordered[k:]
    if not surv or len({c for _, _, c, _ in vic}) != 1:
        return None
    if kind == "d":
        ref = vic[-1][0]
        q1 = min(p - s for p, s, _, _ in surv) - ref
        tops = [(p - ref, s, c) for p, s, c, _ in surv]
    else:
        ref = min(p - s for p, s, _, _ in vic)
        q1 = ref - max(p for p, _, _, _ in surv)
        tops = [(ref - p, s, c) for p, s, c, _ in surv]
    if q1 < 1:
        return None
    return q1, tops


def _fold_step(state: _FoldState, op: _FoldOp) -> _FoldState | None:
    """Apply one concrete op, or ``None`` where the move algebra refuses it.

    The arithmetic mirrors :func:`_fold_moves` -- a wipe relocates its
    victims by ``amount`` and merges them onto one wiped point, the doubling
    scales everything, and the same span guard applies.  Divergence from the
    interpreter is caught downstream either way: the emitter mirrors every
    raw row and asserts at each step, so a plan built on wrong arithmetic
    cannot emit.
    """
    kind, k, amount, _vids = op
    if kind == "m":
        top = max(p for p, _, _, _ in state)
        bot = min(p - s for p, s, _, _ in state)
        if not 0 < (top - bot) * 2 <= 2 * _LIMIT - 2:
            return None
        return _fold_norm([(p * 2, s * 2, c, i) for p, s, c, i in state])
    if k == len(state):
        # The everything-wipe: legal only once a single class remains.
        if len({c for _, _, c, _ in state}) != 1:
            return None
        allids = frozenset(x for _, _, _, i in state for x in i)
        return ((0, 0, state[0][2], allids),)
    frame = _fold_wipe_frame(state, kind, k)
    if frame is None:
        return None
    q1, _tops = frame
    if not _LIMIT + 1 <= amount <= _LIMIT + q1:
        return None
    ordered = sorted(state, key=lambda t: t[0] if kind == "d" else -t[0])
    vic, surv = ordered[:k], ordered[k:]
    merged_vic = (0, 0, vic[0][2], frozenset(x for _, _, _, i in vic for x in i))
    if kind == "d":
        vt = vic[-1][0]
        items = [(p - vt - amount, s, cc, ii) for p, s, cc, ii in surv]
    else:
        vb = min(p - s for p, s, _, _ in vic)
        items = [(amount - (vb - p), s, cc, ii) for p, s, cc, ii in surv]
    items.append(merged_vic)
    hi = max(p for p, _, _, _ in items)
    lo = min(p - s for p, s, _, _ in items)
    if hi - lo > 2 * _LIMIT:
        return None
    return _fold_merge(items)


def _fold_clean_amount(state: _FoldState, kind: str, k: int) -> int | None:
    """Smallest window amount whose landing coincides with no survivor.

    A wipe at exactly ``cmin`` can drop its victims onto a survivor the
    move algebra then refuses to merge -- an opposite class, or a group
    still carrying extent -- which is what used to make a fixed relocation
    amount fail on the packed ladder's irregular gaps.  The window is a full
    interval, so the first free value in it is a computed amount, not a
    searched one.
    """
    frame = _fold_wipe_frame(state, kind, k)
    if frame is None:
        return None
    q1, tops = frame
    occupied = {qt for qt, _s, _c in tops}
    for amount in range(_LIMIT + 1, _LIMIT + q1 + 1):
        if amount not in occupied:
            return amount
    # The window cannot be exhausted: it has ``q1`` slots and the occupied
    # set is the survivor tops, which are distinct positions, so filling it
    # needs ``q1`` survivors -- while ``q1`` is itself the gap to the
    # *nearest* survivor, and packing that many in collapses it to 1.
    # Measured over 47.2M legal wipe frames (sizes 2-4, both directions,
    # every k, mixed spans and classes): no window ever ran out.  The return
    # stays as the total function's last arm.
    return None  # pragma: no cover


def _fold_op(state: _FoldState, kind: str, k: int, amount: int) -> _FoldOp:
    ordered = sorted(state, key=lambda t: t[0] if kind == "d" else -t[0])
    vids = frozenset(x for _, _, _, i in ordered[:k] for x in i)
    return (kind, k, amount, vids)


def _fold_rule_move(state: _FoldState) -> _FoldOp | None:
    """Name the one move the closed-form rules choose from ``state``.

    A fixed case analysis, not a ranking: each case either applies -- and
    then fully determines its move -- or falls through to the next.

    1. One class left: the everything-wipe finishes.
    2. An end group whose landing window holds a same-class wiped point:
       wipe it onto the nearest such point, which is a merge.  This is the
       workhorse -- on a grown ladder it runs as a conveyor, merging one
       group per op until the windows empty.
    3. A same-class run of groups at an end: wipe them together at the
       first collision-free amount, which merges the run onto one point.
    4. Spread at most 3002: double.  Growth is what pushes same-class gaps
       past the 3003 line so case 2's windows fill; it is also the only
       reorder the language has (see :func:`_fold_moves`).
    5. Otherwise hop an end group by the first collision-free amount.  On a
       state wider than 3004 the hop lands inside the pack, compressing the
       spread back under the doubling bound.

    Cases 2 and 5 try the dive side first; ties inside a case take the
    nearest target.  Both choices are conventions -- the r <= 5 mining
    recorded on :func:`_fold_skeleton` found rank ties to be confluent,
    and the acceptance sweeps below re-measure that end to end.
    """
    m = len(state)
    if len({c for _, _, c, _ in state}) == 1:
        return _fold_op(state, "d", m, _LIMIT + 1)
    for kind in ("d", "u"):
        frame = _fold_wipe_frame(state, kind, 1)
        if frame is None:
            continue
        q1, tops = frame
        vcls = (
            min(state, key=lambda t: t[0])[2]
            if kind == "d"
            else max(state, key=lambda t: t[0])[2]
        )
        best = None
        for qt, qspan, qcls in tops:
            in_window = _LIMIT + 1 <= qt <= _LIMIT + q1
            if (
                qspan == 0
                and qcls == vcls
                and in_window
                and (best is None or qt < best)
            ):
                best = qt
        if best is not None:
            return _fold_op(state, kind, 1, best)
    desc = sorted(state, key=lambda t: -t[0])
    k = 1
    while k < m and desc[k][2] == desc[0][2]:
        k += 1
    if 1 < k < m:
        amount = _fold_clean_amount(state, "u", k)
        # ``1 < k < m`` is the clean amount's own precondition.
        if amount is not None:  # pragma: no branch
            return _fold_op(state, "u", k, amount)
    asc = sorted(state, key=lambda t: t[0])
    k = 1
    while k < m and asc[k][2] == asc[0][2]:
        k += 1
    if 1 < k < m:
        amount = _fold_clean_amount(state, "d", k)
        # ``1 < k < m`` is the clean amount's own precondition.
        if amount is not None:  # pragma: no branch
            return _fold_op(state, "d", k, amount)
    top = max(p for p, _, _, _ in state)
    bot = min(p - s for p, s, _, _ in state)
    if 0 < (top - bot) * 2 <= 2 * _LIMIT - 2:
        return ("m", 0, 0, frozenset())
    for kind in ("d", "u"):
        amount = _fold_clean_amount(state, kind, 1)
        if amount is not None:
            return _fold_op(state, kind, 1, amount)
    return None


def _fold_reduce(
    state: _FoldState,
    done: "Callable[[_FoldState], bool]",
    budget: int | None = None,
) -> list[_FoldOp] | None:
    """Run the rules to a ``done`` state, or ``None`` where they dead-end.

    The extent pre-pass comes first, as it always has: a group with extent
    can be neither a landing target nor a merge, so every spanned group is
    wiped once -- at the first collision-free amount rather than a fixed
    ``cmin``, for the same reason as case 5 above.  ``budget`` defaults to
    the derived latency guard recorded on :data:`_FOLD_STEP_SLOPE`; the
    corpus never reaches it, and a rules dead-end returns ``None`` through
    the same refusal path the search used.
    """
    st = _fold_norm(list(state))
    ops: list[_FoldOp] = []
    guard = 0
    while any(s > 0 for _, s, _, _ in st) and len(st) > 1:
        guard += 1
        if guard > 2 * len(state) + 4:  # pragma: no cover - linear in groups
            break
        amount = _fold_clean_amount(st, "d", 1)
        if amount is None:
            break
        wipe = _fold_op(st, "d", 1, amount)
        nb = _fold_step(st, wipe)
        if nb is None:  # pragma: no cover - a clean amount always applies
            break
        ops.append(wipe)
        st = nb
    if budget is None:
        budget = _FOLD_STEP_SLOPE * len(st) + _FOLD_STEP_SLACK
    for _ in range(budget):
        if done(st):
            return ops
        op = _fold_rule_move(st)
        if op is None:
            return None
        nb = _fold_step(st, op)
        if nb is None:
            return None
        ops.append(op)
        st = nb
    return ops if done(st) else None


#: The rule construction's step budget, as ``slope * points + slack``
#: rather than a flat number.  **The starting point count is the run
#: count** -- the fold opens with one point per run of the sorted table, so
#: a budget written against points is written against the table's own
#: structure.
#:
#: **The budget is what guarantees a return.**  Two of the retired
#: descent's termination facts still hold -- ``_fold_merge`` only ever
#: coalesces points, so the count never rises, and every move guards the
#: workspace, so the states at a fixed count are finitely many -- but the
#: third leg was its ``seen`` set, and :func:`_fold_reduce` carries none.
#: The rules are deterministic, so a revisited state would be a true cycle;
#: none was observed anywhere the construction was measured, but nothing
#: forbids one, and the budget converts that possibility into the same
#: ``None`` refusal every other dead end takes.
#:
#: So the slope only has to be generous enough not to cut a reduction short,
#: and its calibration predates the rules: on the retired descent's walks
#: **four inputs was enumerated rather than sampled**: folding all 65534
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
#: above an observed peak that small states, not large ones, produce.  The
#: rules sit further under it than the descent did -- their worst observed
#: ratio is 4.77, at 13 points, over the same corpora plus the 997-group
#: eleven-input state -- so the bound carries over unshrunk.  What makes
#: that acceptable is the termination argument above -- the budget does not
#: decide what builds, only how long a doomed descent runs -- plus the fold
#: being the last route tried, so a loose budget costs refusal latency and
#: nothing on a table that builds.
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
#: ``(top, span, class)`` signatures with a *global* visited set, generating
#: successors with :func:`_fold_moves` at ``kcap=None``.  ``kcap`` does not
#: bind below nine points (``kmax = m if m <= 8``), so this is the shipped
#: move set for every word measured; at ``r >= 9`` the retired descent's
#: ``kcap=3`` was a different graph and is not covered by this rule.
#:
#: The harness's start state is the same object :func:`_fold` builds, and
#: that is checked rather than assumed: over all 65534 non-constant
#: four-input tables, the state constructed from the run-length word alone
#: has the identical signature to the one built from the table, 65534
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


#: Which run-length words the three-phase construction serves.  ``r`` is the
def _fold_served(r: int, delta: int, pat1: int) -> bool:
    """Whether the three-phase construction serves this run-length word.

    ``r`` is the number of runs and the pair is ``(delta, pat[1])``; a word
    this rejects falls through to the rule construction, which is what
    happens for every ``r >= 6``.

    The second clause is not a budget but an identity.  ``delta`` is set
    when every middle index ``{(r - 1) // 2, r // 2}`` of the pattern is
    ``1``, and for ``r`` of 2, 3 and 4 that index set *contains* index 1 --
    so ``delta`` implies ``pat[1]``, and the three keys ``(2, 1, 0)``,
    ``(3, 1, 0)`` and ``(4, 1, 0)`` name states that cannot be built.  The
    converse does not hold and the clause is one-directional: ``(2, 0, 1)``
    and ``(4, 0, 1)`` are both reachable, because a middle index other than
    1 can be the ``0`` that clears ``delta``.  At ``r == 3`` the only middle
    *is* index 1, so there the implication runs both ways and ``(3, 0, 1)``
    is unreachable too.  At ``r == 5`` the middles are ``{2}`` alone, which
    frees index 1 entirely.

    This replaced a twelve-entry table of exactly these keys.  The set was
    recorded as a corpus measurement -- "the four combinations absent here
    never arise" -- but nothing about it depends on a corpus: enumerating
    every pattern to ``r == 12`` reproduces the tabulated set exactly, and
    the four absences are structural.  ``test_fold_served_is_reachability``
    re-derives it.
    """
    if not 2 <= r <= 5:
        return False
    if r == 5:
        return True
    if delta and not pat1:
        return False
    return not (r == 3 and pat1 and not delta)


def _fold_skeleton(r: int, delta: int, pat1: int) -> tuple[tuple[str, int, str], ...]:
    """Plan the reduction of an ``r``-run word: peel, park, close.

    *Peel* the ends inward with alternating ``d1``/``u2`` wipes at ``cmax``,
    *park* with one wipe at ``cmin`` and then double, and *close* with a wipe
    onto a landing followed by ``cmax`` wipes ending at ``k == 2``.  ``delta``
    -- set when the middle runs are long -- adds one peel step, which is the
    ``+1`` of the cost form.  The first move's direction follows which side
    carries the long run: dive when it sits low, rise when high.

    Below four runs the ends meet before the workspace runs out, so there is
    nothing to park and the plan is the peel alone.
    """
    if r == 2:
        opening: list[tuple[str, int, str]] = [("d" if pat1 else "u", 1, "cmax")]
        return tuple(opening + [("d", 1, "cmax")] * delta)
    if r == 3:
        if delta:
            return (("d", 1, "cmax"), ("d", 1, "cmax"), ("d", 2, "cmax"))
        return (("d", 1, "cmax"), ("u", 2, "cmax"))
    # One peel per run past the four the park and close consume, plus one
    # more for delta, alternating direction from the dive that starts it.
    peels = r - 4 + delta
    peel = [("d", 1, "cmax") if i % 2 == 0 else ("u", 2, "cmax") for i in range(peels)]
    park: tuple[str, int, str]
    close: list[tuple[str, int, str]]
    if r == 5 and delta:
        park = ("u", 1, "cmin")
        close = [("u", 1, "cmax"), ("u", 1, "land2"), ("u", 2, "cmax")]
    elif r == 5:
        park = ("u", 2, "cmin")
        close = [("d", 1, "land1"), ("d", 1, "cmax"), ("u", 2, "cmax")]
    elif delta:
        park = ("d", 1, "cmin")
        close = [("d", 1, "cmax"), ("d", 1, "land2"), ("d", 2, "cmax")]
    elif pat1:
        park = ("u", 1, "cmin")
        close = [("d", 1, "land1"), ("d", 1, "cmax"), ("u", 2, "cmax")]
    else:
        park = ("d", 1, "cmin")
        close = [("d", 1, "cmax"), ("u", 1, "land2"), ("u", 2, "cmax")]
    return (*peel, park, ("m", 0, "m"), *close)


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
    :func:`_fold_skeleton` and each amount is solved against the live
    state, so the work is one geometry computation per op.  Returns ``None``
    when the pattern is not tabulated or a step does not resolve, and the
    caller falls through to the rule construction.
    """
    st = _fold_norm(list(state))
    if _fold_done(st):
        return []
    word = tuple(len(ids) for _p, _s, _c, ids in sorted(st, key=lambda t: -t[0]))
    pat = tuple(1 if x > 1 else 0 for x in word)
    r = len(pat)
    mids = {(r - 1) // 2, r // 2}
    delta = 1 if all(pat[i] for i in mids) else 0
    key = (r, delta, pat[1] if r > 1 else 0)
    if not _fold_served(*key):
        return None
    skel = _fold_skeleton(*key)
    ops: list[_FoldOp] = []
    for kind, k, sym in skel:
        got = _fold_resolve(st, kind, k, sym)
        if got is None:
            return None
        op, st = got
        ops.append(op)
    return ops if _fold_done(st) else None


def _fold_plan(state: _FoldState) -> list[_FoldOp] | None:
    """Plan a full reduction, or ``None`` where no rule applies.

    The plan is *constructed* either way now.  Where the table's run-length
    word is one :func:`_fold_served` accepts -- every word of at most
    five runs -- the skeleton names the plan outright, byte-stable with what
    always shipped.  Everywhere else :func:`_fold_reduce` runs the rules of
    :func:`_fold_rule_move` to two points.  The best-first search and the
    greedy descent that stood here are gone: over every state compared --
    all 254 non-constant three-input tables, 200-table four-input and
    150-table five-input samples plus parity, majority and the alternator
    at each -- the rules and the descent accept exactly the same set, and
    every rules-built table re-executes on the interpreter at one fill
    width, three through six inputs, plus eight, ten, eleven, and the
    twelve-input interleaved route.
    """
    built = _fold_construct(state)
    if built is not None:
        return built
    return _fold_reduce(state, _fold_done)


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
        if code is None:
            raise AssertionError(k)
        return code

    def descend(self, k: int) -> None:
        if k == 0:
            return
        if k == 1:
            self.descend(3)
            self.plain_rise(2)
            return
        if k < 2:
            raise AssertionError("k >= 2")
        if not all(v <= _LIMIT for v in self.pos.values()):
            raise AssertionError("all(v <= _LIMIT for v in self.pos.values())")
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
        if k < 2:
            raise AssertionError("k >= 2")
        if not all(-_LIMIT <= v <= _LIMIT for v in self.pos.values()):
            raise AssertionError(
                "all(-_LIMIT <= v <= _LIMIT for v in self.pos.values())"
            )
        if not all(v + k <= _LIMIT for v in self.pos.values()):
            raise AssertionError("all(v + k <= _LIMIT for v in self.pos.values())")
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
        if 2 * spread > 2 * _LIMIT:
            raise AssertionError("2 * spread <= 2 * _LIMIT")
        want_top = 1501
        if next_is_rise:
            # The next command sequence opens with ``p``, which wipes
            # anything below -3003, so the doubled state must fit both ways.
            want_top = max(spread - 1501, 0)
            if want_top > 1501:
                raise AssertionError(spread)
        self.preshift(want_top - top)
        if not all(2 * v <= _LIMIT for v in self.pos.values()):
            raise AssertionError("all(2 * v <= _LIMIT for v in self.pos.values())")
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
        if not vic:
            raise AssertionError(vids)
        if got != vids:
            raise AssertionError(vids)
        return vic

    def dive(self, c: int, vids: frozenset[int]) -> None:
        vic = self._vic(vids)
        if len({self.cls[v] for v in vic}) != 1:
            raise AssertionError("len({self.cls[v] for v in vic}) == 1")
        vt = max(self.pos[v] for v in vic)
        surv = [p for p in self.pos if p not in vic]
        q1 = (min(self.pos[p] for p in surv) - vt) if surv else 40
        if not (_LIMIT + 1 <= c <= _LIMIT + q1):
            raise AssertionError((c, q1))
        d = c + vt
        if d < 2:
            self.preshift(2 - d)
            d = c + max(self.pos[v] for v in vic)
        self.descend(d)
        below = {p for p, v in self.pos.items() if v < -_LIMIT}
        if below != vic:
            raise AssertionError((below, vic))
        self.body.append("pp")
        for p in vic:
            self.pos[p] = 0
        for p in self.pos:
            if not (-_LIMIT <= self.pos[p] <= _LIMIT):
                raise AssertionError("-_LIMIT <= self.pos[p] <= _LIMIT")
        self._land(vic)

    def rise(self, c: int, vids: frozenset[int]) -> None:
        vic = self._vic(vids)
        if len({self.cls[v] for v in vic}) != 1:
            raise AssertionError("len({self.cls[v] for v in vic}) == 1")
        vb = min(self.pos[v] for v in vic)
        surv = [p for p in self.pos if p not in vic]
        q1 = (vb - max(self.pos[p] for p in surv)) if surv else 40
        if not (_LIMIT + 1 <= c <= _LIMIT + q1):
            raise AssertionError((c, q1))
        u = c - vb
        if u < 2:
            self.preshift(-(2 - u))
            u = c - min(self.pos[v] for v in vic)
        if min(self.pos.values()) < -_LIMIT:
            raise AssertionError("min(self.pos.values()) >= -_LIMIT")
        if not all(self.pos[p] + u <= _LIMIT for p in surv):
            raise AssertionError("all(self.pos[p] + u <= _LIMIT for p in surv)")
        self.body.append("p" + self._sub(u) + "p")
        for p in self.pos:
            self.pos[p] += u
        over = {p for p, v in self.pos.items() if v > _LIMIT}
        if over != vic:
            raise AssertionError((over, vic))
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
            if self.cls[o] != c:
                raise AssertionError("cross-class landing")
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
                if self.pos[lo] + u1 > _LIMIT:
                    raise AssertionError("self.pos[lo] + u1 <= _LIMIT")
                self.body.append("p" + self._sub(u1) + "ps")
                for p in self.pos:
                    self.pos[p] += u1
                if self.pos[hi] <= _LIMIT:
                    raise AssertionError("self.pos[hi] > _LIMIT")
                if self.pos[lo] > _LIMIT:
                    raise AssertionError("self.pos[lo] <= _LIMIT")
                self.pos[hi] = 0
                for p in self.pos:
                    self.pos[p] -= 2
                pts = sorted(self.pos, key=lambda q: self.pos[q])
                lo, hi = pts
            gap = self.pos[hi] - self.pos[lo]
            if gap < 258:
                raise AssertionError(gap)
            need = (-(self.byte(hi) - self.byte(lo)) - self.pos[lo]) % 256
            umin = max(_LIMIT + 1 - self.pos[hi], 2)
            umax = _LIMIT - self.pos[lo]
            u = next(
                (c0 for c0 in range(umin, umax + 1) if c0 % 256 == need),
                None,
            )
            if u is None:
                raise AssertionError((umin, umax, need))
            self.body.append("p" + self._sub(u) + "ps")
            for p in self.pos:
                self.pos[p] += u
            if self.pos[hi] <= _LIMIT:
                raise AssertionError("self.pos[hi] > _LIMIT")
            if self.pos[lo] > _LIMIT:
                raise AssertionError("self.pos[lo] <= _LIMIT")
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
            if self.pos[p] % 256 != self.byte(p) % 256:
                raise AssertionError(
                    (
                        self.pos[p],
                        self.cls[p],
                    )
                )
            if self.pos[p] > _LIMIT:
                raise AssertionError("self.pos[p] <= _LIMIT")
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
        if amount <= 0:
            raise AssertionError(amount)
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
        if widened is None:
            raise AssertionError(amount)
        if _apply(0, widened) != -amount:
            raise AssertionError((amount, widened))
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
    The plan is one named move per state -- the case analysis of
    :func:`_fold_rule_move` -- and the emitted program is *checked*, not
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


def _fold_to_cofactors(state: _FoldState) -> list[_FoldOp] | None:
    """Merge equal suffix cofactors, leaving distinct ones separate.

    This is deliberately a small-state bridge: it is used between
    placeholders, where equal cofactors have already reduced the live
    state.  The final two-answer reduction still goes through
    :func:`_fold_plan`.

    The size gate is unchanged and still costs no reach.  Exhaustively over
    ``n <= 4`` -- 33628 tables build -- no successful build ever hands this
    a state above eight points, and the constructed adversaries that grow
    the state on purpose (a function of only the first ``k`` inputs embedded
    at ``n = 8, 10, 12``, and a middle window whose growth starts late) top
    out at four.  A miss here aborts the candidate outright, so refusing a
    larger state changes no output -- only how fast a doomed arity gives up.

    Behind the gate the old best-first search is replaced by the same rules
    that plan the whole fold, aimed at :func:`_cofactor_done` -- one wiped
    point per distinct cofactor -- instead of two points.  Over every bridge
    state the instrumented routes hand in (658, from the documented
    adversaries plus all 256 three-input tables forced through the route)
    the rules and the search accept exactly the same set: 301 solved, zero
    lost, zero gained.
    """
    start = _fold_norm(list(state))
    if _cofactor_done(start):
        return []
    if len(start) > _COFACTOR_BRIDGE_POINTS:
        return None
    return _fold_reduce(start, _cofactor_done)


def _fold_span(state: _FoldState) -> int:
    """Return ``state``'s occupied top-to-bottom extent."""
    return max(point for point, _, _, _ in state) - min(
        point - extent for point, extent, _, _ in state
    )


def _split_setter(total: int) -> tuple[str, str, int, int] | None:
    """Spell an up/down setter pair whose moves sum to ``total``."""
    middle = total // 2
    for up in range(max(2, middle - 8), min(total - 1, middle + 8) + 1):
        down = total - up
        pair = _pad_pair(_affine_code(1, up), _affine_code(1, -down))
        if pair is not None:
            zero, one = pair
            return zero, one, up, down
    return None


def _centred_setter(span: int) -> tuple[str, str, int, int] | None:
    """Separate a span with equal-width upward and downward setters."""
    return _split_setter(span + 2)


def _interleaved_final_pair(truth_table: str, n: int) -> str | None:
    """Build a table by laying a prefix ladder and folding the final two inputs.

    The all-row fold ends at eleven inputs by counting: ``2**12`` distinct
    positions span at least 4095, past what any laid ladder can hold.  This
    route never holds all rows apart.  The first ``n - 2`` inputs lay as a
    ladder whose points carry four-row cofactors; the next input splits them
    into two-row cofactors -- at most four *distinct* ones -- which the fold
    merges class by class; the last input splits the survivors into answer
    bits for the ordinary two-class endgame.  Merging by cofactor class
    rather than answer bit is what keeps every wipe's victim block
    class-homogeneous, so the reduce is thousands of cheap merges rather
    than the one-per-doubling starvation an answer-keyed interleave hits.

    The prefix ladder is picked by the same rule the all-row fold uses: the
    narrow uniform ladder while its footprint fits the workspace (ten
    inputs, so twelve-input tables), and the packed distinct-subset-sum
    ladder past that (eleven, so thirteen).  Fourteen inputs would need a
    twelve-input prefix, and no ladder lays ``2**12`` distinct positions
    inside the footprint -- the same counting wall, one stage later.
    """
    prefix = n - 2
    narrow = _fold_uniform(prefix, _FOLD_NARROW_STEP)
    weights = narrow if sum(narrow) <= _LIMIT else _fold_subset_weights(prefix)
    if weights is None:
        return None
    setters = _fold_setters(prefix, weights)
    positions = _fold_positions(prefix, weights)
    emitter = _FoldEmitter.__new__(_FoldEmitter)
    emitter.table = truth_table
    emitter.rows = 2**n
    block = 2 ** (n - prefix)
    emitter.pos = {
        frozenset(range(row * block, (row + 1) * block)): positions[row]
        for row in range(2**prefix)
    }
    emitter.cls = {
        key: truth_table[row * block : (row + 1) * block]
        for row, key in enumerate(emitter.pos)
    }
    emitter.body = ["{X" + str(index) + "}" for index in range(prefix)]

    def lay(index: int, *, cofactor: bool) -> tuple[str, str] | None:
        lo = min(emitter.pos.values())
        hi = max(emitter.pos.values())
        span = hi - lo
        if weights is narrow:
            got = _centred_setter(span)
        else:
            # A compacted state's points can span past 3001, where disjoint
            # bands no longer fit the workspace -- and with class-many
            # points they are not needed.  Two children collide only when
            # their parents sit exactly ``up + down`` apart, so the first
            # even total that is no pair's distance splits collision-free,
            # the same computed value the wipe rules land on.  Odd totals
            # never spell: the identity has no odd-width hold.
            dists = {
                b - a
                for a in emitter.pos.values()
                for b in emitter.pos.values()
                if b > a
            }
            got = None
            # The range holds more even totals than there are distances,
            # so a free one always exists and the loop always breaks --
            # and `_split_setter` spells every total it is handed here.
            for total in range(4, 2 * len(dists) + 8, 2):  # pragma: no branch
                if total in dists:
                    continue
                got = _split_setter(total)
                if got is not None:  # pragma: no branch
                    break
        if got is None:
            return None
        zero, one, up, down = got
        shift = -_LIMIT - lo + down
        if shift > _LIMIT - hi - up:
            return None
        emitter.preshift(shift)
        next_pos: dict[_FoldKey, int] = {}
        next_cls: dict[_FoldKey, str] = {}
        occupied: dict[int, str] = {}
        for key, value in emitter.pos.items():
            rows = set(key) if isinstance(key, frozenset) else {key}
            for bit, code in ((0, zero), (1, one)):
                picked = {row for row in rows if (row >> (n - 1 - index)) & 1 == bit}
                # No known table reaches this: a merged key would have to
                # hold rows agreeing on the bit being laid, and the reduce
                # merges by cofactor class, which splits on exactly that
                # bit.  320 random tables at three to ten inputs, every
                # documented shape, and the low-bit-ignoring families all
                # miss it.
                if not picked:  # pragma: no cover - see above
                    continue
                value2 = _apply(value, code)
                if not -_LIMIT <= value2 <= _LIMIT:
                    return None
                cls = (
                    _cofactor_class(truth_table, n, next(iter(picked)), index + 1)
                    if cofactor
                    else truth_table[next(iter(picked))]
                )
                if value2 in occupied and occupied[value2] != cls:
                    return None
                occupied[value2] = cls
                key2: _FoldKey = (
                    next(iter(picked)) if len(picked) == 1 else frozenset(picked)
                )
                next_pos[key2] = value2
                next_cls[key2] = cls
        emitter.pos, emitter.cls = next_pos, next_cls
        emitter.body.append("{X" + str(index) + "}")
        return zero, one

    def state() -> _FoldState:
        return _fold_norm(
            [
                (
                    value,
                    0,
                    emitter.cls[key],
                    key if isinstance(key, frozenset) else frozenset({key}),
                )
                for key, value in emitter.pos.items()
            ]
        )

    def emit(ops: list[_FoldOp]) -> None:
        for index, (kind, _, amount, rows) in enumerate(ops):
            if kind == "m":
                emitter.double(
                    next_is_rise=index + 1 < len(ops) and ops[index + 1][0] == "u"
                )
            elif kind == "d":
                emitter.dive(amount, rows)
            else:
                emitter.rise(amount, rows)

    if weights is not narrow:
        # The packed ladder lays its rows at *unit* gaps, so every landing
        # window is one already-occupied amount and the first wipe has no
        # collision-free landing; the split below would double the points
        # and put the span past the doubling bound, freezing that jam in.
        # Compacted first -- one point per four-row cofactor, at most
        # sixteen -- the state still spans only the ladder, where the
        # doubling fires and regrows the gaps the conveyor needs, and every
        # later stage works on class-many points rather than row-many.
        compact = state()
        # Sixteen live classes rather than two: case 2's window only ever
        # serves its own class, so the conveyor hops more between merges --
        # measured 11.3 ops per starting point where the two-class corpus
        # fits slope 8.  Doubling the slope keeps the guard linear and the
        # refusal path intact.
        packed = _fold_reduce(
            compact,
            _cofactor_done,
            budget=2 * _FOLD_STEP_SLOPE * len(compact) + _FOLD_STEP_SLACK,
        )
        if packed is None:
            return None
        emit(packed)
    first = lay(prefix, cofactor=True)
    if first is None:
        return None
    setters.append(first)
    partial = _fold_reduce(state(), _cofactor_done)
    if partial is None:
        return None
    emit(partial)
    second = lay(prefix + 1, cofactor=False)
    if second is None:
        return None
    setters.append(second)
    final = _fold_plan(state())
    if final is None:
        return None
    emit(final)
    emitter.finish()
    header = ";".join(
        f"{index}={zero}|{one}" for index, (zero, one) in enumerate(setters)
    )
    return header + _HEADER_END + "".join(emitter.body)


def _interleaved_fold(truth_table: str, n: int) -> str | None:
    """Try a placeholder/fold/placeholder build before the all-row fallback.

    Every ``{Xi}`` appears once and in name order, but unlike :func:`_fold_at`
    its setter is emitted immediately before the cofactor fold it enables.
    The emitter mirrors every raw row, so a returned candidate is checked at
    every reset and landing just like the shipped ladder path.

    The current bridge deliberately accepts only compactable intermediate
    states; it is an executable replacement skeleton, not yet the large-state
    gap controller.  A miss lets the established fold try its ladders.
    """
    if n in (12, 13):
        staged = _interleaved_final_pair(truth_table, n)
        # Every twelve- and thirteen-input table the suite builds is served
        # by the pair; a miss would fall through to the ladders below.
        if staged is not None:  # pragma: no branch
            return staged
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
        # need a new rung at all, and identity branches keep a late ignored
        # input from re-expanding a compacted state merely to collapse it
        # again.  Where a split remains, one current span plus a
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
                if not picked:  # pragma: no cover - both branches always populated
                    # A group is a *union* of rows -- it starts as all of them
                    # and only ever merges -- so it is never filtered on an
                    # input it has not consumed yet, and both values of that
                    # input are always present.  Measured over 24186 groups
                    # (all n=2 and n=3 tables, 400 random tables at n=4..6):
                    # none was constant on the bit being split.
                    continue
                code = one if bit else zero
                new_value = _apply(value, code)
                if not -_LIMIT <= new_value <= _LIMIT:
                    return None
                suffixes = {
                    _cofactor_class(truth_table, n, row, index + 1) for row in picked
                }
                if len(suffixes) != 1:  # pragma: no cover - the merge invariant
                    # This is the inductive fact the comment above names, and
                    # it holds by construction: groups are keyed by their
                    # suffix cofactor, so a group's rows already share one,
                    # and splitting it on the next input refines that key
                    # rather than mixing two.  Measured over 1772 tables (all
                    # n=2 and n=3, 500 random at n=4..6): never violated.  The
                    # check stays as the assertion that keeps it honest.
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
    if final is None:  # pragma: no cover - a done state is never refused
        # Every state reaching here is already ``_fold_done`` (see below), and
        # ``_fold_plan`` on a done state returns the empty plan rather than
        # refusing: ``_fold_reduce`` checks the done condition before it looks
        # for a move.  Measured over 4000 constructed done states: never
        # ``None``.  The check stays as the caller's half of the contract.
        return None
    # ``final`` is always empty, so this loop never has a body to run: by the
    # last placeholder every row has been merged onto its cofactor's single
    # point, which is exactly ``_fold_done``, and ``_fold_plan`` returns the
    # empty plan for a state that already satisfies it.  Measured: every one
    # of 164 states reaching ``_fold_plan`` here was already done on arrival
    # (all n=2 and n=3 tables exhaustively, random tables at n=4..11).  The
    # loop stays because the emptiness is a property of the *state*, not of
    # this call -- a future stage that left work behind would need it.
    for kind, _, amount, row_ids in final:  # pragma: no cover
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

    **The ladder is bounded by ``_LIMIT``, not ``2 * _LIMIT``.**  The plan
    state is relative -- :func:`_fold_moves` allows a *span* of ``2 * _LIMIT``
    because a state may sit anywhere in ``[-_LIMIT, _LIMIT]`` -- but the
    emitter lays the rows at absolute positions starting from a zero
    accumulator, so the ladder itself has to fit in ``[-_LIMIT, _LIMIT]``.
    Checking only the relative bound lets the planner spend thousands of moves on
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
    if len(set(pos)) != len(pos):
        raise AssertionError((n, weights))
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
    for index, bit in enumerate(bits):
        zero, one = branches[index]
        body = body.replace("{X" + str(index) + "}", one if bit else zero)
    return body
