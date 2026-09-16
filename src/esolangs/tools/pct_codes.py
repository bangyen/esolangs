"""The %^2^-1 instruction spellings every construction is built from.

Every route below emits the same two primitives -- an affine setter branch and
a subtraction of a chosen size -- so they are spelled once here, along with the
template-format constants :func:`~esolangs.tools.pct_squared_minus_one.fill`
reads and the byte values ``e`` prints as digits.
"""

import re
from functools import cache

#: The accumulator is zeroed when it exceeds this, checked before each command.
_LIMIT = 3003


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


#: Byte values ``e`` prints as ``"0"`` and ``"1"``.  Unlike ``l``, which prints
#: the accumulator in decimal and so needs it to *be* 0 or 1, ``e`` prints
#: ``chr(acc & 0xFF)`` -- the accumulator only has to be *congruent* to these
#: mod 256, which is what lifts the ceiling every other path runs into.
_BYTE_ZERO = 48
_BYTE_ONE = 49
