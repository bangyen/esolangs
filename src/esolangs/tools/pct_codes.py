"""The %^2^-1 instruction spellings the fold is built from."""

import re

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

    ``s`` subtracts 2 and ``i`` 3, so only ``k == 1`` has no spelling.
    """
    if k == 0:
        return ""
    if k == 1:
        return None
    if k % 2 == 0:
        return "s" * (k // 2)
    return "i" + "s" * ((k - 3) // 2)


def _short_sub_code(k: int) -> str | None:
    """Return the shortest straight descent by ``k``, if it is spellable."""
    if k == 0:
        return ""
    if k == 1:
        return None
    threes = k // 3
    if (k - 3 * threes) % 2:
        threes -= 1
    return "i" * threes + "s" * ((k - 3 * threes) // 2)


def _sub_with(k: int, threes: int) -> str | None:
    """Subtract ``k`` spending exactly ``threes`` ``i`` commands, or ``None``.

    Trading ``s`` for ``i`` is how a caller reaches the other width parity.
    """
    rest = k - 3 * threes
    if rest < 0 or rest % 2:
        return None
    return "i" * threes + "s" * (rest // 2)


def _affine_code(a: int, b: int) -> str | None:
    """Return a command string realising ``x -> a*x + b``, or ``None``.

    A positive offset is spelled as a negated subtraction, ``-(-x - b)``.
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

    The over-3003 reset fires *before* each command.
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

    A ``None`` branch propagates.  Unequal widths leak the input through
    ``len()``; the pad is ``pp``, two executed negations composing to the
    identity, so a pass stripping ignored characters cannot reintroduce
    the leak.  An odd shortfall returns ``None``.
    """
    if zero is None or one is None:
        return None
    gap = len(one) - len(zero)
    if gap % 2:
        return None
    if gap > 0:
        return zero + "p" * gap, one
    return zero, one + "p" * (-gap)


#: Byte values ``e`` prints as ``"0"`` and ``"1"``.  Unlike ``l``, which prints
#: the accumulator in decimal and so needs it to *be* 0 or 1, ``e`` prints
#: ``chr(acc & 0xFF)`` -- the accumulator only has to be *congruent* to these
#: mod 256, which is what lets a deep class print.
_BYTE_ZERO = 48
_BYTE_ONE = 49
