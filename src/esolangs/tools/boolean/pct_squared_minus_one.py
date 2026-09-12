r"""Build parameterized Boolean programs for %^2^-1."""

import re
from collections.abc import Callable, Iterator
from functools import cache
from itertools import chain, pairwise

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["pct_squared_minus_one"]

# : The accumulator is zeroed.
_LIMIT = 3003

# : Affine multipliers a setter.
_A_VALS = (1, -1, 0, 2)

# : Offsets considered for a.
# : magnitude past 8 (XOR's.
# : statement about the.
_OFFSETS = range(-10, 11)

# : Accumulator values the.
# : The tail has to move these.
# : with one translation, which.
# : are the only pairs that.
_CLASS_PAIRS = tuple(
    (zero, one) for zero in range(-9, 10) for one in range(-9, 10) if zero != one
)

# : Separates the setter header.
# :.
# : A *blank line*, not a.
# : rows like the body: a.
# : two it falls in, and only.
# : blank line inside either.
# : empty row -- so the.
# :.
# : This is a template-format.
# : never sees a header;.
_HEADER_END = "\n\n"

# : Matches one setter.
_DECL_RE = re.compile(r"(\d+)=([^|;]*)\|([^;]*)")


def _sub_code(k: int) -> str | None:
    r"""Return code subtracting exactly ``k >= 0``, or ``None`` if."""
    if k == 0:
        return ""
    if k == 1:
        return None
    if k % 2 == 0:
        return "s" * (k // 2)
    return "i" + "s" * ((k - 3) // 2)


def _sub_with(k: int, threes: int) -> str | None:
    r"""Subtract ``k`` spending exactly ``threes`` ``i`` commands, or."""
    rest = k - 3 * threes
    if rest < 0 or rest % 2:
        return None
    return "i" * threes + "s" * (rest // 2)


def _affine_code(a: int, b: int) -> str | None:
    r"""Return a command string realising ``x -> a*x + b``, or ``None``."""
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
    r"""Run ``code`` on ``acc`` exactly as ``_Machine.step`` would."""
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
    r"""Pad two setter branches to equal width, preserving each one's value."""
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
    r"""Return a tail printing ``1`` from ``one_value`` and ``0`` from."""
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
        # The shift was solved from.
        # rather than selects -- 236.
        # range all pass it.
        # tail evidence rather than.
        if (  # pragma: no branch - the arithmetic above cannot produce a miss
            _apply(one_value, body) == 1 and _apply(zero_value, body) == 0
        ):
            return body + "l"

    return None


# : The class pairs that.
# : :data:`_CLASS_PAIRS`.
# : ``p``, so it exists only.
# : the other -- and even then.
# : for a shift of 1, which is.
# : and ``(-1, -2)`` out of the.
# :.
# : This is a *filter on dead.
# : :func:`_solution` ends with.
# : ``None`` when it misses, so.
# : :func:`_derive`'s ``best``,.
# : comprehension preserves.
# : candidate of a given width,.
# : Skipping the other 310 is.
# : 619k :func:`_solution`.
# : end to end on the.
# : 0.37s).
# : hoisting inside it was.
_VIABLE_CLASS_PAIRS = tuple(
    pair for pair in _CLASS_PAIRS if _tail_for(pair[1], pair[0]) is not None
)


def _column_slopes(rows: dict[tuple[int, int], int]) -> list[list[int]]:
    r"""Return the admissible slopes per column, read straight off the."""
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
    r"""Solve the offset a column needs, or ``None`` if it is inconsistent."""
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
    r"""Assemble a full program from one candidate parameter set, or reject."""
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
    r"""Derive the shortest program for a two-input table."""
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


# : Setter branches for the.
# : characters wide, so a.
# : parity problem never.
# : odd shortfall against an.
# : ``pp`` is two negations,.
# : then negates zero, which is.
_CASCADE_IDENT = "pp"
_CASCADE_ERASE = "'p"

# : Loads 1 into the.
# : 3, ``s`` subtracts 2.
# : has no representation for 1.
_CASCADE_ONE = "ips"


# : Negates a 0/1 accumulator:.
# : subtracts 2, so ``r``.
# : the indicator into its.
# : ``NAND``-``n``.
# : which builds 1 from an.
_CASCADE_NOT = "ips"


def _subcube_of(truth_table: str, n: int) -> dict[int, int] | None:
    r"""Return the literals pinning ``truth_table``'s ON-set, or ``None``."""
    ones = [index for index, bit in enumerate(truth_table) if bit == "1"]
    if not ones:
        return None
    rows = [tuple((index >> (n - 1 - k)) & 1 for k in range(n)) for index in ones]
    fixed = {k: rows[0][k] for k in range(n) if len({row[k] for row in rows}) == 1}
    # A subcube on ``len(fixed)``.
    # a table with the right.
    if len(ones) != 2 ** (n - len(fixed)):
        return None
    return fixed


def _cascade(truth_table: str, n: int) -> str | None:
    r"""Build a cascade template, or ``None`` if the table is not a subcube."""
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


# : Multipliers the wide search.
# : ``p`` (negate) over the.
# : erase.
# :.
# : Written as the closure.
# : because the bound is the.
# : reaches no further table,.
# : is what the two commands.
# : required because the wide.
# : behaves: ascending.
_WIDE_A_LIMIT = 4


def _wide_a_vals(limit: int) -> tuple[int, ...]:
    r"""Return the reachable multipliers up to ``limit``, in search order."""
    powers = []
    value = 1
    while value <= limit:
        powers.append(value)
        value *= 2
    return (0, *(signed for p in powers for signed in (p, -p)))


_WIDE_A_VALS = _wide_a_vals(_WIDE_A_LIMIT)

# : Offsets the wide search.
# : no table that ``+/-12``.
_WIDE_B_VALS = tuple(range(-12, 13))

# : Window a candidate spelling.
# : because it *behaves* as.
# : which is what lets ``mp``.
_SPELL_WINDOW = range(-90, 91)

# : Longest command string the.
_SPELL_MAX = 7


# : The alphabet a branch.
_SPELL_ALPHABET = "simp'"


def _spell_map(window: tuple[int, ...]) -> tuple[int, int] | None:
    r"""Return ``(a, b)`` if ``window`` is ``a*x + b`` throughout, else."""
    first, second = window[0], window[1]
    a = second - first
    b = first - a * _SPELL_WINDOW[0]
    pairs = zip(_SPELL_WINDOW, window, strict=True)
    if any(value != a * x + b for x, value in pairs):
        return None
    return a, b


@cache
def _spell_bases() -> dict[tuple[int, int], tuple[str | None, str | None]]:
    r"""Minimal spelling of each grid map, per width parity."""
    window = tuple(_SPELL_WINDOW)
    shortest: dict[tuple[tuple[int, int], int], str] = {}
    # The empty string is the.
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
                # The erase forgets the prefix,.
                # every width above its own and.
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
    r"""Map width to a command string realising ``x -> a*x + b`` at that."""
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
            # All 25 single-parity maps in.
            # returned above, so both bases.
            # The guard stays because it is.
            # a future base table with a.
            # it here rather than pad a.
            continue
        for width in range(len(base), _SPELL_MAX + 1, 2):
            out[width] = base + "pp" * ((width - len(base)) // 2)
    return out


# : One branch of a setter as.
_Branch = tuple[int, int]


# : Ladders the search runs, as.
# : of 250 and every rung stays.
# : one exactly affine: the.
# : accumulator, so no rung.
# :.
# : These eight are a *cover*,.
# : four bases leaves 256.
# : other paths miss; greedy.
# : between them reach all.
# :.
# : The cover is minimal --.
# : for the first three, two.
# : removing the ladder path.
# : characters over the twenty.
# : majority-of-three going 874.
# :.
# : **What keeping eight rather.
# : build time.** An earlier.
# : about fifty seconds;.
# : cover's 0.01s.
# : 26 -- and every one of.
# : widening would only move.
# : change, which is the reason.
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

# : Longest suffix the ladder.
# : the shipped grid need at.
# : this bounds the frontier.
_LADDER_DEPTH = 10


def _sub_of_width(k: int, width: int) -> str | None:
    r"""Spell a subtraction of exactly ``k`` in ``width`` characters, or."""
    eyes = k - 2 * width
    esses = width - eyes
    if eyes < 0 or esses < 0:
        return None
    return "i" * eyes + "s" * esses


def _even_width_for(k: int) -> int | None:
    r"""Narrowest *even* width at which ``k`` has a subtraction spelling."""
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
    r"""Spell a ladder's stage one, or ``None`` if some weight has no."""
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
        if code is None:  # pragma: no cover - the width just spelled it
            return None
        setters.append(("p" * width, code))
    return setters, lead


def _ladder_vector(
    setters: list[tuple[str, str]], lead: str, n: int
) -> tuple[int, ...]:
    r"""Return what stage one really leaves, run rather than solved."""
    out = []
    for index in range(2**n):
        code = lead
        for position, (zero, one) in enumerate(setters):
            code += one if (index >> (n - 1 - position)) & 1 else zero
        out.append(_apply(0, code))
    return tuple(out)


# : The five comparators the.
# : ``(cut, slope)`` -- the two.
# : :func:`_ladder_gadget`.
# : threshold on the rung's.
# : second stage reaches, which.
# : ``ceil(3004 / slope)``;.
# : the cut (plus rung 0, when.
# : band between the thresholds.
# : cover with the same status.
# : twenty tables need was.
# : The spellings themselves.
# : claimed deriving them meant.
# : composition is forced (see.
# : strings now live in the.
# :.
# : Five pairs suffice for the.
# : every comparator the.
# : slope reaches, 83 gadgets.
# : serves nothing these five.
# : fold never lists, but every.
# : and four would flip from.
# : so the wider family buys.
_LADDER_CUTS = ((3004, 4), (1502, 4), (1500, 4), (751, 8), (3004, 8))


def _sub_units(units: int) -> str:
    r"""Shortest ``s``/``i`` spelling of a subtraction of ``units``."""
    # Unspellable; silence would.
    if units == 1:
        raise AssertionError("units != 1")
    if units % 3 == 0:
        return "i" * (units // 3)
    if units % 3 == 2:
        return "i" * (units // 3) + "s"
    return "i" * (units // 3 - 1) + "ss"


def _ladder_gadget(cut: int, slope: int) -> str:
    r"""Spell the comparator with outer threshold ``cut`` and scale."""
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

# : How a gadget finishes:.
# : inverts it first, so the.
_LADDER_TAILS = ("sl", "ipl")


@cache
def _ladder_built() -> dict[str, tuple[int, str]]:
    r"""Every table the ladder path serves: table to ``(ladder, suffix)``."""
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
    r"""Build a ladder template, or ``None`` if the table is not one."""
    if n != 3:
        # Every shipped ladder has.
        # tabulation froze was empty at.
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


# : Byte values ``e`` prints as.
# : the accumulator in decimal.
# : ``chr(acc & 0xFF)`` -- the.
# : mod 256, which is what.
_BYTE_ZERO = 48
_BYTE_ONE = 49

# : The band construction's.
# : congruent mod 256 and the.
_BAND_UNIT = 256

# : Where a band construction.
# : the next stage's translate.
# : under it that parking.
_BAND_PARK = 2000


# : How far the deep band's.
# : where the measured coverage.
# : over weightings rather than.
#: not a program space.
_DEEP_CAP = 6

# : Where the deep band parks.
# : the limit, so a later cut's.
_DEEP_PARK = 2000


def _deep_values(n: int, units: tuple[int, ...], mask: int) -> list[int]:
    r"""Row values for a weighting, with ``mask`` naming the complemented."""
    return [
        sum(
            u * _BAND_UNIT * (((r >> (n - 1 - k)) & 1) ^ ((mask >> k) & 1))
            for k, u in enumerate(units)
        )
        for r in range(2**n)
    ]


def _deep_plan(truth_table: str, n: int, values: list[int]) -> str | None:
    r"""Derive a deep band's body for one value vector, or ``None``."""
    rows = range(2**n)
    groups: dict[int, set[str]] = {}
    for row in rows:
        groups.setdefault(values[row], set()).add(truth_table[row])
    # Two rows sharing a value can.
    # across classes would emit a.
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
        # The first prefix that spells.
        # loop always returns on that.
        if body is not None:  # pragma: no branch
            return body
    return None  # pragma: no cover


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
    r"""Spell one deep-band schedule, or ``None`` if a stage will not close."""
    rows = range(2**n)
    dropped = _sub_code(drop) if drop else ""
    if dropped is None:  # pragma: no cover - the caller chose a spellable drop
        return None
    # The ladder subtracted, so one.
    # the drop carried past the.
    body = dropped + "p"
    # Rows collapse onto their.
    # more than the span budget.
    # not once per row.
    moved = {-v: _apply(-v, dropped + "p") for v in set(values)}
    current = {r: moved[-values[r]] for r in rows}
    if {r for r in rows if current[r] > _LIMIT} != set(order[:prefix]):
        return None  # pragma: no cover - screened by legality
    cleared = set(order[:prefix])
    for row in cleared:
        # Empty from the screened.
        # ``prefix == 0`` -- measured.
        # inputs, 1332 bodies, all of.
        # past the limit and there is.
        # planner's own handling of a.
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
        # A wiped band thereafter takes.
        # so the parking cancels from.
        # cut: the translation is.
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
    # Nearest zero first: a shift.
    # taking the smallest keeps the.
    # from -80 residue systems up.
    # ten-thousand-character run of.
    for shift in sorted((base + _BAND_UNIT * reps for reps in range(-8, 9)), key=abs):
        tail = _affine_code(1, shift)
        if tail is None:
            continue  # pragma: no cover - screened by legality
        shifted = {v: _apply(v, tail) for v in set(current.values())}
        printed = {r: shifted[v] for r, v in current.items()}
        # A band reaching here has a.
        # the first spellable tail.
        if all(  # pragma: no branch
            (printed[r] & 0xFF) == (_BYTE_ONE if truth_table[r] == "1" else _BYTE_ZERO)
            for r in rows
        ):
            return body + tail + "e"
    return None  # pragma: no cover


def _deep_setters(
    units: tuple[int, ...], mask: int
) -> tuple[tuple[str, str], ...] | None:
    r"""Spell one setter per input, both branches at a common width."""
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
        # The hold branch is ``pp``.
        # identity, so both branches.
        # program leaks its inputs.
        setters.append((hold, code) if not (mask >> index) & 1 else (code, hold))
    return tuple(setters)


def _cross_class_diffs(truth_table: str, n: int) -> list[tuple[int, ...]]:
    r"""Difference vectors of the row pairs a weighting must keep apart."""
    # A diff is the disjoint bit.
    # row has a 1 the second lacks,.
    # packed int each and only the.
    # ``lead > 0`` says the top.
    seen: set[int] = set()
    size = 2**n
    for row in range(size):
        for other in range(row + 1, size):
            if truth_table[row] == truth_table[other]:
                continue
            # ``other > row``, so the.
            # always other's: ``other &.
            # ``row & ~other``, and the.
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
    r"""Whether no cross-class pair collides under this weighting."""
    for diff in diffs:
        total = 0
        for k, unit in enumerate(units):
            total += -unit * diff[k] if (mask >> k) & 1 else unit * diff[k]
        if total == 0:
            return False
    return True


@cache
def _deep_weightings(n: int) -> tuple[tuple[int, ...], ...]:
    r"""Return the unit vectors worth trying, cheapest span first."""
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
    by_sum[0].clear()  # the all-zero tuple, the one.
    for bucket in by_sum:
        bucket.sort(key=lambda u: (max(u), u))
    return tuple(chain.from_iterable(by_sum))


def _deep_band(truth_table: str, n: int) -> str | None:
    r"""Build a deep-band template, or ``None`` if no weighting schedules."""
    if n > _LIMIT // _BAND_UNIT:
        # Each unit prices a whole.
        # weighting costs ``n * 256``.
        # eleven inputs.
        # only symmetric tables pass.
        # table that ignores an input.
        # already served.
        # enumeration below -- a.
        # whose every survivor the.
        return None
    if n > 4 and any(
        len({truth_table[r] for r in range(2**n) if bin(r).count("1") == pop}) > 1
        for pop in range(n + 1)
    ):
        return None
    diffs = _cross_class_diffs(truth_table, n)
    # A singleton diff -- rows.
    # ``±units[k]`` under every.
    # there is illegal at all masks.
    # any.
    # (any coordinate can carry a.
    # everything past the screen.
    # the C-speed ``0 in units``.
    # 24219 weightings ordered.
    # have a zero unit, so the.
    singles = {diff.index(1) for diff in diffs if sum(map(abs, diff)) == 1}
    full_screen = len(singles) == n
    for units in _deep_weightings(n):
        if full_screen:
            if 0 in units:
                continue
        elif any(not units[k] for k in singles):
            continue
        for mask in range(2**n):
            # Legality decides the.
            # weighting whose collisions.
            # been observed to fail here --.
            # span budget were scheduled.
            # replaces planning as the.
            # below runs once rather than.
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

# : The ladder spacing tried.
# :.
# : **What bounded the fold was.
# : rows start at ``-step *.
# : the emitter has to lay it.
# : At the wide spacing that is.
# : workspace, so no such table.
# : planner searched.
# : is exactly what happened:.
# : the emitter would refuse,.
# : unmerged.) Halving the.
# : and ten inputs then build.
# :.
# : Two is the floor.
# : :func:`_sub_code` spells.
# : the last input to subtract.
# : With 2 the floor, ``2 *.
# : inputs.
# : itself the waste, and.
# : spending only what.
# :.
# : It is a *fallback* rather.
# : is built on the wider.
# : plans the same tables but.
# : on a miss keeps every.
# : confines the change to the.
_FOLD_NARROW_STEP = 2

# : The packed ladder: ``(2, 3,.
# :.
# : **A uniform ladder wastes.
# : to sit at ``2**n``.
# : merged by the first cut.
# : but a uniform ladder buys.
# : 1)``, which is far more.
# : is a set of weights whose.
# : cheapest such set spans.
# :.
# : The floor is easy to state.
# : integers, so the largest is.
# : (``2a + 3b`` cannot spell.
# : sums to ``S - 1``.
# : and ``S >= 2**n + 1``.
# : cover the small residues.
# : a weight of 1, and the.
# : ``2**n`` sums are distinct.
# :.
# : That is what lifts the.
# : eleven inputs against the.
# : **2049**, and eleven inputs.
# : does not fit, so this shape.
# : reaches thirteen, since.
# : positions a ``p``-negated.
# :.
# : **Row order stops matching.
# : the rest of the fold had.
# : ``-step * r``, so.
# : are contiguous; with these.
# : (weight 16).
# : position rather than over.
# : plan search, the moves, the.
#: needed no change.
# : The value is the ladder's.
# : powers;.
# : They are what meets the.
# : ``2 * (2**n - 1)``, and it.
# : weight of 1 would otherwise.
_FOLD_SUBSET_LADDER = (2, 3)

# : One point of a fold plan:.
# : row value relative to the.
# : (0 once it has been wiped.
_FoldPoint = tuple[int, int, str, frozenset[int]]
_FoldState = tuple[_FoldPoint, ...]

# : One move: ``(kind, k, c,.
# : wipe the bottom/top ``k``.
_FoldOp = tuple[str, int, int, frozenset[int]]

# : The largest bridge state.
# : not chosen: exhaustively.
# : hand the bridge more than.
# : the state (a function of.
# : 12``) top out at four.
# : a 512-point state burned.
# : for 192s -- while.
#: paid for.
_COFACTOR_BRIDGE_POINTS = 8

# : A point in the emitter's.
_FoldKey = int | frozenset[int]


def _fold_norm(items: list[_FoldPoint]) -> _FoldState:
    r"""Sort by top descending and rebase so the highest top is 0."""
    ordered = sorted(items, key=lambda t: (-t[0], t[1]))
    top = ordered[0][0]
    return tuple((p - top, s, c, i) for p, s, c, i in ordered)


def _fold_merge(items: list[_FoldPoint]) -> _FoldState | None:
    r"""Coalesce equal positions, or ``None`` on a cross-class collision."""
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
    r"""Yield every candidate move from ``state``."""
    m = len(state)
    kmax = m if (kcap is None or m <= 8) else min(m, kcap)
    top_all = max(p for p, _, _, _ in state)
    bot_all = min(p - s for p, s, _, _ in state)
    spread = top_all - bot_all
    # Doubling needs the whole.
    # odd spread of 3003 has no.
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
            # The span check above is the.
            # pair that passes it always.
            if merged is not None:  # pragma: no branch
                yield (
                    "u",
                    k,
                    amount,
                    frozenset(x for _, _, _, i in vic for x in i),
                    merged,
                )


def _fold_done(state: _FoldState) -> bool:
    r"""Two wiped points at most: one value per class, nothing unmerged."""
    return len(state) <= 2 and all(t[1] == 0 for t in state)


def _fold_wipe_frame(
    state: _FoldState, kind: str, k: int
) -> tuple[int, list[tuple[int, int, str]]] | None:
    r"""Return ``(q1, survivor tops)`` for a wipe, or ``None`` if it is."""
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
    r"""Apply one concrete op, or ``None`` where the move algebra refuses."""
    kind, k, amount, _vids = op
    if kind == "m":
        top = max(p for p, _, _, _ in state)
        bot = min(p - s for p, s, _, _ in state)
        if not 0 < (top - bot) * 2 <= 2 * _LIMIT - 2:
            return None
        return _fold_norm([(p * 2, s * 2, c, i) for p, s, c, i in state])
    if k == len(state):
        # The everything-wipe: legal.
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
    r"""Smallest window amount whose landing coincides with no survivor."""
    frame = _fold_wipe_frame(state, kind, k)
    if frame is None:
        return None
    q1, tops = frame
    occupied = {qt for qt, _s, _c in tops}
    for amount in range(_LIMIT + 1, _LIMIT + q1 + 1):
        if amount not in occupied:
            return amount
    # The window cannot be.
    # set is the survivor tops,.
    # needs ``q1`` survivors --.
    # *nearest* survivor, and.
    # Measured over 47.2M legal.
    # every k, mixed spans and.
    # stays as the total function's.
    return None  # pragma: no cover


def _fold_op(state: _FoldState, kind: str, k: int, amount: int) -> _FoldOp:
    ordered = sorted(state, key=lambda t: t[0] if kind == "d" else -t[0])
    vids = frozenset(x for _, _, _, i in ordered[:k] for x in i)
    return (kind, k, amount, vids)


def _fold_rule_move(state: _FoldState) -> _FoldOp | None:
    r"""Name the one move the closed-form rules choose from ``state``."""
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
        # ``1 < k < m`` is the clean.
        if amount is not None:  # pragma: no branch
            return _fold_op(state, "u", k, amount)
    asc = sorted(state, key=lambda t: t[0])
    k = 1
    while k < m and asc[k][2] == asc[0][2]:
        k += 1
    if 1 < k < m:
        amount = _fold_clean_amount(state, "d", k)
        # ``1 < k < m`` is the clean.
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
    r"""Run the rules to a ``done`` state, or ``None`` where they dead-end."""
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


# : The rule construction's.
# : rather than a flat number.
# : count** -- the fold opens.
# : a budget written against.
#: structure.
# :.
# : **The budget is what.
# : descent's termination facts.
# : coalesces points, so the.
# : workspace, so the states at.
# : third leg was its ``seen``.
# : The rules are.
# : none was observed anywhere.
# : forbids one, and the budget.
# : ``None`` refusal every.
# :.
# : So the slope only has to be.
# : and its calibration.
# : **four inputs was.
# : non-constant four-input.
# : against the 144 this budget.
# : exhaustive population, not.
# : table is regular: the.
# : the worst ratio peaks at.
# :.
# : Sampling at wider arities.
# : points) and, importantly,.
# : observed ratio rose with.
# : the slope is not presented.
# : above an observed peak that.
# : rules sit further under it.
# : ratio is 4.77, at 13.
# : eleven-input state -- so.
# : that acceptable is the.
# : decide what builds, only.
# : being the last route tried,.
# : nothing on a table that.
# :.
# : **What the cost actually.
# : exhaustive rather than.
# : lengths, every one of the.
# : 32767 at four map to a.
# : 65534 tables share those.
# : complement -- the cost is.
# : table beyond the word.
# :.
# : The dependence is on the.
# : of the 2248.
# : cost-invariant.
# : run count and class sizes.
# : otherwise alternating word.
# : table shape, three times.
# : worst tables in the whole.
# : alternating with a single.
# :.
# : **All of the above is about.
# : not an invariant of.
# : the order.
# : makes each step depend on.
# : distance.
# : signatures with a global.
# : three-input words, and can.
# : descent takes 9 steps on.
# :.
# : Against the true distance.
# : a fixed run count the.
# : (spread 1, against the.
# : the exact run lengths at.
# : ambiguity at every run.
# : used to record is a fact.
# : exact lengths that "matter.
# :.
# : **The optimal cost has a.
# : and calling a slot *long*.
# :.
# : cost(word) = 2 * r - 3 - (r.
# :.
# : where the *middle* slots.
# : odd ``r``, two for even.
# : minimum cost at that run.
# : The bracket is the.
# : spread above is exactly.
# :.
# : **Definitions, because the.
# : wrong.** ``cost`` is the.
# : one point per run, at.
# : ``_FOLD_STEP * (len - 1)``.
# : ``(top, span, class)``.
# : successors with.
# : bind below nine points.
# : move set for every word.
# : ``kcap=3`` was a different.
# :.
# : The harness's start state.
# : that is checked rather than.
# : four-input tables, the.
# : has the identical signature.
# : of 65534.
# : complement share one --.
#: comes from.
# :.
# : Measured over **1091 words.
# : inputs for ``r <= 6`` (all.
# : words, the ones with the.
# : over ``>1``-patterns at.
# : carried by several words.
# : killed the earlier.
# : words at five and six.
# : rule is most likely to get.
# : extreme mass contrasts, the.
# :.
# : The delta is pinned at the.
# : ``r == 6`` the middle is a.
# : matters: at four inputs.
# : each cost 9 with one middle.
# : 10 with both.
# : ``(1, 1, 1, 2, 1, 1, 25)``.
# : with no solution and depth.
# : present at a run count no.
# : against ``base(7) == 10``,.
# : ``(2, 1, 1, 1, 1, 1, 1)``.
# : (1.17M states, 344s and.
# : ``(1, 1, 1, 1, 1, 1, 26)``.
#: plan at depth 10.
# :.
# : **The delta's mechanism,.
# : points requires an.
# : span*: the wipe collapses.
# : survivor keeps its span,.
# : anything whose span is.
# : ``desc[:k]`` -- 8116 of.
# : long *middle* run is the.
# : dragging a neighbour, so it.
# : necessary condition on all.
# : them admitting a one-move.
# :.
# : The earlier telling of this.
# : keeping straight: a ``k >=.
# : (414 of 840 partial sweeps.
# : requirement lives in the.
# :.
# : The ``base(r)`` half is.
# : plans gives ``r - 1 + 2 *.
# : ``floor((r - 2) / 2)``.
# : ``d``; ``(1, 1, 14)`` is.
# : ``d, m, d, u, u``; ``(1, 1,.
# : three ``u``.
# : the count tracks how often.
# : mechanism sketch, not a.
# : validated by measurement,.
#: derived.
# :.
# : **Four recorded.
# : corrected here.** Every.
# : path length, not against a.
# : ``(19, 2, 11)`` and ``(23,.
# : ``(10, 20, 34)`` both cost.
# : both cost 6.
# : recodings were never.
# : -slot rule's supposed death.
# : ``(1, 14, 1)`` costs 3.
# : says, against the claim.
# : recorded ``base`` table was.
# : 0 at four inputs -- a.
# : start state has a nonzero.
# :.
# : What this does *not* say:.
# : was measured (``r <= 5`` at.
# : and ``r >= 8`` is untested.
# : closed form's prediction,.
# : costs about six minutes and.
# : compute question rather.
# :.
# : One law was found and.
# : three-input maxima exactly,.
# : -- four inputs violate it.
# : the tight small-arity fit.
#: the shape of the algorithm.
# :.
# : One thing measured and.
# : descent's move generation.
# : long plateaus, but that.
# : real descent starts from.
# : Instrumenting the shipped.
# : -- median 1.92, worst 5.10.
# :.
# : Substituting it for the.
# : 387 tables at three through.
# : byte-identical, every one.
# : *not* enough it lifts an.
# : used 359 steps, so nine.
# : tables, where the derived.
# :.
# : What it is not any more is.
# : **Plan length is not.
# : wrong objective.** Ops have.
# : dive at 3004 costs 1490.
# : the accumulator is already.
# : over a thousand.
# : spelled in unary --.
# : count barely correlates.
# : to 6 was measured to save.
#: directly saves 60% and more.
# :.
# : **The cost model is closed.
# : constructible three-input.
# : emitter's position updates,.
# : single congruence -- ``need.
# : whose unique in-window.
# : plan can therefore be.
# :.
# : That model explains a fact.
# : complement-invariant,.
# : 49, so which class lands on.
# : by 2 mod 256 -- about 127.
# : complement ``10011000``.
# :.
# : **One construction ships.
# : table builds from three.
# : characters against this.
# : enumerated optimum, each.
# : row correct at one fill.
#: lengths and of the arity.
# :.
# : Three attempts to.
# : retried.
# : looked like a 27.7% win and.
# : build -- the apparent.
# : tables, at 116/254 coverage.
# : observed optimal shapes,.
# : wide the amount branching.
# : of 40 at a mean of **-67%**.
# : cost-to-go term; the choice.
_FOLD_STEP_SLOPE = 8
_FOLD_STEP_SLACK = 16


# : Which run-length words the.
def _fold_served(r: int, delta: int, pat1: int) -> bool:
    r"""Whether the three-phase construction serves this run-length word."""
    if not 2 <= r <= 5:
        return False
    if r == 5:
        return True
    if delta and not pat1:
        return False
    return not (r == 3 and pat1 and not delta)


def _fold_skeleton(r: int, delta: int, pat1: int) -> tuple[tuple[str, int, str], ...]:
    r"""Plan the reduction of an ``r``-run word: peel, park, close."""
    if r == 2:
        opening: list[tuple[str, int, str]] = [("d" if pat1 else "u", 1, "cmax")]
        return tuple(opening + [("d", 1, "cmax")] * delta)
    if r == 3:
        if delta:
            return (("d", 1, "cmax"), ("d", 1, "cmax"), ("d", 2, "cmax"))
        return (("d", 1, "cmax"), ("u", 2, "cmax"))
    # One peel per run past the.
    # more for delta, alternating.
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
    r"""Return ``(cmin, cmax, survivor tops, victim class)`` for a wipe."""
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
    r"""Turn one symbolic step into a concrete move on ``state``."""
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
    r"""Emit a plan from the state's run-length word, or ``None``."""
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
    r"""Plan a full reduction, or ``None`` where no rule applies."""
    built = _fold_construct(state)
    if built is not None:
        return built
    return _fold_reduce(state, _fold_done)


class _FoldEmitter:
    r"""Exact mirror of every row's accumulator, emitting body characters."""

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
            # The next command sequence.
            # anything below -3003, so the.
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
        # Any next command's pre-check.
        # that flush explicit and costs.
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
        r"""Set the one residue that matters and align the print."""
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
            # Unreachable here, unlike in.
            # block just put ``hi`` at 0.
            # by 2, so ``room`` is exactly.
            # residue mod 256.
            # loop stays because the.
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
    r"""Return the uniform ladder as a weight vector: ``acc = -step * r``."""
    return tuple(step * 2 ** (n - 1 - i) for i in range(n))


def _fold_setters(n: int, weights: tuple[int, ...]) -> list[tuple[str, str]]:
    r"""One subtracting branch per input; the hold matches it in width."""
    out = []
    for i in range(n):
        amount = weights[i]
        if amount <= 0:
            raise AssertionError(amount)
        code = _sub_code(amount)
        if code is not None and len(code) % 2 == 0:
            out.append(("p" * len(code), code))
            continue
        # Odd (or unspellable) width:.
        # same amount at the next even.
        # back through a ``p``-wrapped.
        # ``sub(amount + k) + "p" +.
        # the two respellings, but it.
        # inside the reset line; the.
        # .
        # ``_sub_code`` alone never.
        # as it can, so both halves.
        # odd for every ``k``.
        # them move 6 in two characters.
        # is what changes the parity.
        # ``ii`` subtracts 6, ``pssp``.
        # of 2, against ``pppppp``.
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
            # The overshoot negates, and.
            # leaves the accumulator at.
            # reset line, so the next.
            # nets ``+k`` instead of.
            # amounts in 3002..6008 fails.
            # :func:`_interleaved_fold`.
            # 3000 -- where this used to.
            # .
            # Trading ``s`` for ``i`` at.
            # it only ever descends, so the.
            # magnitude.
            # character less, which is what.
            # is tried second because the.
            # where both apply, and every.
            # built on it -- 1, 2, 3 and 7.
            # all and are exactly the.
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
    r"""Build a fold template, or ``None`` if no plan is found."""
    for weights in _fold_ladders(n):
        built = _fold_at(truth_table, n, weights)
        if built is not None:
            return built
    return None


def _fold_ladders(n: int) -> list[tuple[int, ...]]:
    r"""Return the ladders to try, in order, for an ``n``-input table."""
    out = [_fold_uniform(n, _FOLD_STEP), _fold_uniform(n, _FOLD_NARROW_STEP)]
    packed = _fold_subset_weights(n)
    if packed is not None:
        out.append(packed)
    return out


def _fold_subset_weights(n: int) -> tuple[int, ...] | None:
    r"""Return the packed distinct-subset-sum ladder, or ``None`` past its."""
    # The tail starts one past the.
    # subset sum distinct: a power.
    # can never be matched by them.
    head = _FOLD_SUBSET_LADDER
    start = sum(head) - 1
    weights = (*head, *(start * 2**i for i in range(n - len(head))))
    return weights if sum(weights) <= _LIMIT else None


def _cofactor_class(truth_table: str, n: int, row: int, laid: int) -> str:
    r"""Return ``row``'s suffix cofactor after the first ``laid`` inputs."""
    width = 2 ** (n - laid)
    prefix = row >> (n - laid)
    return truth_table[prefix * width : (prefix + 1) * width]


def _cofactor_done(state: _FoldState) -> bool:
    r"""Whether one wiped point remains for every live suffix cofactor."""
    return all(span == 0 for _, span, _, _ in state) and len(
        {cls for _, _, cls, _ in state}
    ) == len(state)


def _fold_to_cofactors(state: _FoldState) -> list[_FoldOp] | None:
    r"""Merge equal suffix cofactors, leaving distinct ones separate."""
    start = _fold_norm(list(state))
    if _cofactor_done(start):
        return []
    if len(start) > _COFACTOR_BRIDGE_POINTS:
        return None
    return _fold_reduce(start, _cofactor_done)


def _fold_span(state: _FoldState) -> int:
    r"""Return ``state``'s occupied top-to-bottom extent."""
    return max(point for point, _, _, _ in state) - min(
        point - extent for point, extent, _, _ in state
    )


def _split_setter(total: int) -> tuple[str, str, int, int] | None:
    r"""Spell an up/down setter pair whose moves sum to ``total``."""
    middle = total // 2
    for up in range(max(2, middle - 8), min(total - 1, middle + 8) + 1):
        down = total - up
        pair = _pad_pair(_affine_code(1, up), _affine_code(1, -down))
        if pair is not None:
            zero, one = pair
            return zero, one, up, down
    return None


def _centred_setter(span: int) -> tuple[str, str, int, int] | None:
    r"""Separate a span with equal-width upward and downward setters."""
    return _split_setter(span + 2)


def _interleaved_final_pair(truth_table: str, n: int) -> str | None:
    r"""Build a table by laying a prefix ladder and folding the final two."""
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
            # A compacted state's points.
            # bands no longer fit the.
            # points they are not needed.
            # their parents sit exactly.
            # even total that is no pair's.
            # the same computed value the.
            # never spell: the identity has.
            dists = {
                b - a
                for a in emitter.pos.values()
                for b in emitter.pos.values()
                if b > a
            }
            got = None
            # The range holds more even.
            # so a free one always exists.
            # and `_split_setter` spells.
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
                # No known table reaches this:.
                # hold rows agreeing on the bit.
                # merges by cofactor class,.
                # bit.
                # documented shape, and the.
                # miss it.
                if not picked:  # pragma: no cover - both branches always populated
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
        # The packed ladder lays its.
        # window is one.
        # collision-free landing; the.
        # and put the span past the.
        # Compacted first -- one point.
        # sixteen -- the state still.
        # doubling fires and regrows.
        # later stage works on.
        compact = state()
        # Sixteen live classes rather.
        # serves its own class, so the.
        # measured 11.3 ops per.
        # fits slope 8.
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
    r"""Try a placeholder/fold/placeholder build before the all-row."""
    if n in (12, 13):
        staged = _interleaved_final_pair(truth_table, n)
        # Every twelve- and.
        # by the pair; a miss would.
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
        # A live cofactor that takes.
        # need a new rung at all, and.
        # input from re-expanding a.
        # again.
        # gap of two keeps the 0 and 1.
        # binary weight for inputs.
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
        # A previously merged cofactor.
        # the same branch retain one.
        # inductive fact the merge.
        by_value: dict[tuple[int, str], set[int]] = {}
        for group_key, value in emitter.pos.items():
            raw = set(group_key) if isinstance(group_key, frozenset) else {group_key}
            for bit in (0, 1):
                picked = {row for row in raw if (row >> (n - 1 - index)) & 1 == bit}
                if not picked:  # pragma: no cover - both branches always populated
                    # A group is a *union* of rows.
                    # and only ever merges -- so it.
                    # input it has not consumed.
                    # input are always present.
                    # (all n=2 and n=3 tables, 400.
                    # none was constant on the bit.
                    continue
                code = one if bit else zero
                new_value = _apply(value, code)
                if not -_LIMIT <= new_value <= _LIMIT:
                    return None
                suffixes = {
                    _cofactor_class(truth_table, n, row, index + 1) for row in picked
                }
                if len(suffixes) != 1:  # pragma: no cover - the merge invariant
                    # This is the inductive fact.
                    # it holds by construction:.
                    # suffix cofactor, so a group's.
                    # and splitting it on the next.
                    # rather than mixing two.
                    # n=2 and n=3, 500 random at.
                    # check stays as the assertion.
                    return None
                cls = next(iter(suffixes))
                by_value.setdefault((new_value, cls), set()).update(picked)
        # A position collision across.
        # distinction before the.
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
    # After the last placeholder a.
    # two-class plan and residue.
    final = _fold_plan(_fold_norm(final_items))
    if final is None:  # pragma: no cover - a done state is never refused
        # Every state reaching here is.
        # ``_fold_plan`` on a done.
        # refusing: ``_fold_reduce``.
        # for a move.
        # ``None``.
        return None
    # ``final`` is always empty, so.
    # last placeholder every row.
    # point, which is exactly.
    # empty plan for a state that.
    # of 164 states reaching.
    # (all n=2 and n=3 tables.
    # loop stays because the.
    # this call -- a future stage.
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


# : A two-sided ladder was.
# : the positive-ladder band.
# : setter, spelled ``p sub(k).
# : so the ``p``-repeated hold.
# : moves half the rows above.
# : ``[-_LIMIT, _LIMIT]``.
# : it lays 4096 distinct rows.
# :.
# : It still serves nothing,.
# : resource**: the plan needs.
# : span at least 4095 wherever.
# : and the guard refuses a.
# : 4099-wide start has only.
# : the doubling is offered.
# : a span past 3002 can never.
# : proves is needed to reorder.
# : across five arities are.
# : packed one.


def _fold_positions(n: int, weights: tuple[int, ...]) -> list[int]:
    r"""Where each row's accumulator sits after the setters have run."""
    out = []
    for r in range(2**n):
        total = 0
        for i in range(n):
            if (r >> (n - 1 - i)) & 1:
                total += weights[i]
        out.append(-total)
    return out


def _fold_at(truth_table: str, n: int, weights: tuple[int, ...]) -> str | None:
    r"""Build a fold template on a given ladder, or ``None``."""
    pos = _fold_positions(n, weights)
    # Two rows sharing a position.
    # never be separated again, so.
    # one.
    # :func:`_fold_ladders`, not a.
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


# : How many candidate.
# : shortest program among.
# : Both are budgets on *output.
# : candidate that solves.
# : model admits is built at.
# : arity, ``(12, 6)`` is where.
# : enumeration this replaced;.
#: 36 -> 41.
_CANDIDATES = 12
_SPELLINGS = 6

# : Steps between the classes.
# : the rows sit before the.
# : a smaller spread spells.
# : tends to produce the.
_STEPS = (1, 2, 3, 4, -1, -2, 6, -3, 8, 12, -4)


def _solve_affine(values: tuple[int, ...], wanted: tuple[int, ...]) -> _Branch | None:
    r"""Solve ``a * v + b == p`` over the grid, or ``None`` if unsolvable."""
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
    r"""Every way the first two setters produce ``values``."""
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
    r"""Which pre-vector entries may share a value."""
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
    r"""Build a composed-affine template, or ``None`` if the table is not."""
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
        # Cheapest first: a setter's.
        # subtracts, so the smallest.
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
    r"""Spell three solved setters as a template, or ``None``."""
    setters = []
    for zero_branch, one_branch in (first, second, third):
        zero_widths = _spellings_by_width(*zero_branch)
        one_widths = _spellings_by_width(*one_branch)
        shared = set(zero_widths) & set(one_widths)
        if not shared:  # pragma: no cover - every grid branch spells at 6 and 7
            # Measured over all 7 * 25.
            # of them has a spelling at.
            # branches share at least those.
            # grid is a constant that could.
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
    r"""Build a %^2^-1 template for the given truth table."""
    n = _validate_truth_table(truth_table)
    if n > 2:
        # Above two inputs the.
        # slope per column of a.
        # does, at any arity.
        # than served by a program.
        # The cascade covers every.
        # shorter -- ``2n + 4``.
        # *Usually* is not always, so.
        # the two are built and the.
        # sight served 44 of 256 tables.
        # path gives, by up to 7.
        # Building both over that.
        # returning early, since a.
        # path would have done -- the.
        cascade = _cascade(truth_table, n)
        # Tables that are not subcubes.
        # setter per input, which is.
        # .
        # Only at three.
        # composition frontier grows 90.
        # so a four-input table costs.
        # ends up served -- parity-4.
        # deep band that serves it.
        # this path reaches above three.
        # rather than paid for; at.
        affine = _affine(truth_table, n) if n == 3 else None
        # Ties keep the cascade, which.
        best = min(
            (build for build in (cascade, affine) if build is not None),
            key=len,
            default=None,
        )
        if best is not None:
            return best
        # Everything above is affine in.
        # rows that do not already.
        # uses the over-3003 reset as a.
        # majority.
        # far -- hundreds of characters.
        ladder = _ladder(truth_table, n)
        if ladder is not None:
            return ladder
        # Every path above prints with.
        # exactly 0 or 1.
        # residue mod 256 matters --.
        # into as many bands as the.
        # subtraction, so the whole.
        # cannot fire, and rows of one.
        # three and four inputs total.
        deep = _deep_band(truth_table, n)
        if deep is not None:
            return deep
        # The deep band still reads the.
        # weighting, and from five.
        # collides rows of opposite.
        # drops the weighting.
        # (each wipe moves a group by.
        # doubling regrows gaps) that.
        # only the final two-point gap.
        # a full residue system as its.
        fold = _fold(truth_table, n)
        if fold is None:
            # The staged route is.
            # at the arities they already.
            # while beyond them it is the.
            # equal suffix cofactors before.
            fold = _interleaved_fold(truth_table, n)
        # Reaching this raise means no.
        # and the staged cofactor route.
        # emitting nothing is better.
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
    # Widen a one-input table by.
    # present in the derivation but.
    widened = truth_table if n == 2 else "".join(bit * 2 for bit in truth_table)
    derived = _derive(widened)
    # Every one- and two-input.
    # finds a realisable parameter.
    # derivation rather than a.
    if derived is None:
        raise AssertionError(f"no %^2^-1 derivation for truth table {truth_table!r}")
    setters, tail = derived
    if n == 1:
        # A widened table cannot depend.
        # two branches carry the same.
        # placeholder.
        # silently dropping a branch.
        # for the wrong function.
        zero, one = setters[1]
        # The widened table repeats.
        # the answer and its two.
        if zero != one:
            raise AssertionError(
                f"one-input derivation split on input 1: {truth_table!r}"
            )
        setters, tail = setters[:1], zero + tail
    header = ";".join(f"{k}={zero}|{one}" for k, (zero, one) in enumerate(setters))
    body = "".join("{X" + str(k) + "}" for k in range(n)) + tail
    return header + _HEADER_END + body


def fill(template: str, bits: list[int]) -> str:
    r"""Instantiate ``template`` for ``bits``, returning a runnable program."""
    header, _, body = template.partition(_HEADER_END)
    header = header.replace("\n", "")
    branches = {
        int(m.group(1)): (m.group(2), m.group(3)) for m in _DECL_RE.finditer(header)
    }
    for index, bit in enumerate(bits):
        zero, one = branches[index]
        body = body.replace("{X" + str(index) + "}", one if bit else zero)
    return body
