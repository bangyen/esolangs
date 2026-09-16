"""The %^2^-1 threshold-ladder route.

One of the strategies :func:`~esolangs.tools.pct_squared_minus_one` tries: a
run of weighted rungs that stays exactly affine inside ``[-_LIMIT, 0]``, so the
reset never fires until the suffix asks it to.
"""

from functools import cache

from esolangs.tools.pct_codes import (
    _HEADER_END,
    _apply,
    _even_width_for,
    _sub_of_width,
)

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
