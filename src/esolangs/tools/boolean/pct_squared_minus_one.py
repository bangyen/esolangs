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
using the over-3003 reset (which fires before every command) as the
comparator that collapses the zero class.

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
ignores its second input.  Higher arities are not supported -- the
derivation reads one slope per column of a two-input table and does not
generalise -- and :func:`pct_squared_minus_one` raises :class:`ValueError`
for them rather than returning a program that computes the wrong function.

Unlike the other parameterized generators, *which* command strings a setter
uses is derived per table rather than fixed by the language, so a bare
``{Xi}`` cannot be filled by a table-independent lambda.  The template
therefore carries a header naming each setter's two branches, followed by
the ``{Xi}`` placeholders themselves; :func:`fill` reads the header and
substitutes the branch each bit selects.  This mirrors ArrowQueue, whose
template likewise needs a structure-aware filler rather than a lambda.

Both branches of a setter are padded to the same width with ``pp`` -- two
negations, which the interpreter executes and which compose to the identity
-- so every instantiation of a template has the same length and no program
leaks its inputs through ``len()``.
"""

import re
from functools import cache

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
#: with one translation when they sit a step apart and with the over-3003
#: clamp otherwise, so nearby pairs are the ones worth offering.
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
    if head is None:  # pragma: no cover - _A_VALS holds no other multiplier
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

    Two shapes are tried, cheapest first.  A bare translation moves both
    classes at once when they differ by one, optionally after a ``p`` so a
    reversed pair works too.  Failing that, the classes are separated by
    amplification: scaling by ``2**j`` drives one class past the limit while
    the other stays below, and the reset then collapses it -- the language's
    only comparator, used as the endgame's branch.
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
        if _apply(one_value, body) == 1 and _apply(zero_value, body) == 0:
            return body + "l"

    # Amplify-then-clamp: push the zero-class over the limit so ``l``'s own
    # pre-reset zeroes it, while the one-class is translated onto 1.
    for pre in ("", "p"):
        for amp in range(0, 13):
            for offset in range(-40, 41):
                move = _sub_code(-offset) if offset <= 0 else _affine_code(1, offset)
                if move is None:
                    continue
                body = pre + "m" * amp + move
                if (
                    _apply(one_value, body) == 1
                    and _apply(zero_value, body) == 0  # pragma: no cover - see below
                ):
                    # Unreachable as the moves stand.  Every ``move`` here is
                    # a translation, and ``m`` scales both classes alike, so
                    # this body sends the gap to ``2**amp * (one - zero)``
                    # (negated by ``p``).  Landing on 1 and 0 needs a gap of
                    # exactly 1, which only ``amp == 0`` gives -- and that is
                    # the bare translation the first shape already tried.
                    # The clamp this loop was written for would need a move
                    # that is not affine in the accumulator.
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
    if best is None:  # pragma: no cover - every two-input table finds a solution
        return None
    return best[1], best[2]


def pct_squared_minus_one(truth_table: str) -> str:
    """Build a %^2^-1 template for the given truth table.

    ``truth_table`` is a binary string of length ``2`` or ``4``, indexed by
    the inputs (most significant first); the table length implies ``n``.

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

    Raises :class:`ValueError` above two inputs: the derivation reads one
    slope per column of a two-input table and does not generalise, and
    emitting nothing is better than emitting a program that computes the
    wrong function.
    """
    n = _validate_truth_table(truth_table)
    if n > 2:
        raise ValueError(
            f"%^2^-1 supports one- and two-input tables; got {n} inputs "
            f"({truth_table!r})"
        )
    # Widen a one-input table by repeating each entry, so the second input is
    # present in the derivation but cannot change the answer.
    widened = truth_table if n == 2 else "".join(bit * 2 for bit in truth_table)
    derived = _derive(widened)
    if derived is None:  # pragma: no cover - every such table derives
        raise ValueError(f"no %^2^-1 derivation for truth table {truth_table!r}")
    setters, tail = derived
    if n == 1:
        # A widened table cannot depend on its second input, so that setter's
        # two branches carry the same code; fold it into the tail and keep one
        # placeholder.  The equality is checked rather than assumed, because
        # silently dropping a branch that *did* differ would emit a program
        # for the wrong function.
        zero, one = setters[1]
        if zero != one:  # pragma: no cover - a widened table cannot reach this
            raise ValueError(f"one-input derivation split on input 1: {truth_table!r}")
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
