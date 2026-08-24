"""Shared helpers for the text generators."""

from collections.abc import Iterable


def _ilog(base: int, n: int) -> int:
    """Floor of log_base(n), computed with integers to avoid float error."""
    k = 0
    while base ** (k + 1) <= n:
        k += 1
    return k


def _factor_triple(value: int) -> tuple[int, int, int]:
    """Return ``(a, b, r)`` with ``value == a * b + r`` and minimal ``a + b + r``.

    The generators use a multiplication loop to build a byte value: a run of
    ``a`` then a run of ``b`` multiplies (``a * b``), and a final run of
    ``r`` tops the product up.  The ``a`` that minimizes ``a + b + r`` is
    found by scanning ``a`` up to ``sqrt(value)``, so the program is
    O(sqrt) rather than O(value).
    """
    best = min(
        (
            (a + b + r, a, b, r)
            for a in range(1, int(value**0.5) + 2)
            for b, r in (divmod(value, a),)
        ),
    )
    _, a, b, r = best
    return a, b, r


def _require_bytes(text: str, name: str) -> None:
    """Reject any character outside the 0-255 byte range.

    The byte-oriented cross-check interpreters emit one byte per character, so
    a generator that builds byte values would silently corrupt codepoints
    above 255.  Fail loudly instead.
    """
    if any(ord(c) > 255 for c in text):
        raise ValueError(f"{name} can only output bytes 0-255")


def _literal_chunks(text: str, width: int | None, overhead: int) -> list[str]:
    """Split ``text`` so each chunk plus ``overhead`` fits in ``width``.

    The literal languages (3x, Eval, Modulous, MyScript) print by embedding
    the text in a statement, so their program is one long line that no
    after-the-fact reflow can break: a newline inside the literal is a
    character the program goes on to print.  Splitting the *text* instead
    and emitting one statement per chunk gives the same output in a program
    that fits the width, which is the same trick the 2D generators use --
    honour a width by building a different shape rather than by reflowing a
    finished one.

    ``overhead`` is the per-statement cost (3x's two brackets, Modulous's
    push and print instructions).  A width too small to fit that plus one
    character still yields one character per chunk rather than an empty one,
    so the caller gets an over-wide line instead of a program that loops
    forever -- the same escape hatch an oversized token gets elsewhere.
    """
    if width is None or width <= 0:
        return [text]
    size = max(1, width - overhead)
    return [text[i : i + size] for i in range(0, len(text), size)]


def _require_ascii(text: str, name: str) -> None:
    """Reject any character outside the 0-127 ASCII range.

    Some interpreters keep a 7-bit accumulator or parity, so values above 127
    wrap and would be printed as the wrong byte.  Fail loudly instead.
    """
    if any(ord(c) > 127 for c in text):
        raise ValueError(f"{name} can only output ASCII (0-127)")


# The build plan for every Collatz Multiverse constant: ``_PLAN[n]`` is
# ``(needed, decompositions)`` where ``needed`` is the smallest set of
# constants (beyond k1/k2) required to build ``k n`` and ``decompositions``
# maps each such constant to the ``(b, a, c)`` it is built from.
_PLAN: dict[int, tuple[frozenset[int], dict[int, tuple[int, int, int]]]] = {
    1: (frozenset(), {}),
    2: (frozenset(), {}),
}


def _extend_plans(maxval: int) -> None:
    """Fill ``_PLAN`` up to ``maxval`` with minimal two-line build plans.

    A Collatz Multiverse line ``v = a x + b`` applies the Collatz rule to
    ``v``'s current value: an odd (or zero) value becomes ``value * a + b``
    and an even value halves.  A fresh register (value 0) therefore copies
    any built constant ``b`` with ``v = negativeOne x + b``, and when the
    copied value is *odd* a second line ``v = a x + c`` turns it into
    ``b * a + c``.  Each constant costs two lines once its operands exist, so
    a value ``n`` is reachable as ``b * a + c`` with an odd ``b``.  This
    reaches large values in O(log) constants instead of the +1/+2 chain.
    """
    for m in range(3, maxval + 1):
        if m in _PLAN:
            continue
        best: tuple[frozenset[int], dict[int, tuple[int, int, int]]] | None = None
        for b in range(1, m, 2):
            for a in range(1, min(m // b + 1, m)):
                rem = m - b * a
                need = frozenset({m}) | _PLAN[b][0] | _PLAN[a][0]
                if rem > 2:
                    need |= _PLAN[rem][0]
                if best is None or len(need) < len(best[0]):
                    best = (need, {m: (b, a, rem)})
        if best is None:
            raise AssertionError("b = 1 always yields a finite plan")
        plan = dict(best[1])
        for v in best[0]:
            if v >= 3 and v != m:
                plan.update(_PLAN[v][1])
        _PLAN[m] = (best[0], plan)


def _cm_constants(needed: Iterable[int]) -> list[str]:
    """Lines building Collatz Multiverse constants for the values in ``needed``.

    ``k1``/``k2`` are bootstrapped from ``negativeOne``, then each further
    constant is built by the two-line multiply-add trick from
    :func:`_extend_plans` (``k{n} = negativeOne x + k{b}`` copies the odd
    ``b``, ``k{n} = k{a} x + k{c}`` multiplies it by ``a`` and adds ``c``).
    Only the constants the program actually references are built, rather than
    a full ``1..maxval`` chain.
    """
    need = sorted(n for n in set(needed) if n > 2)
    lines = [
        "k1 = negativeOne x + negativeOne, NOT PRINT.",
        "k1 = negativeOne x + zero, NOT PRINT.",
        "k2 = negativeOne x + negativeOne, NOT PRINT.",
        "k2 = negativeOne x + k1, NOT PRINT.",
    ]
    if not need:
        return lines
    _extend_plans(max(need))
    total: frozenset[int] = frozenset()
    decomp: dict[int, tuple[int, int, int]] = {}
    for n in need:
        s, d = _PLAN[n]
        total |= s
        decomp.update(d)
    for n in range(3, max(need) + 1):
        if n in total:
            b, a, c = decomp[n]
            lines.append(f"k{n} = negativeOne x + k{b}, NOT PRINT.")
            if c == 0:
                lines.append(f"k{n} = k{a} x + zero, NOT PRINT.")
            else:
                lines.append(f"k{n} = k{a} x + k{c}, NOT PRINT.")
    return lines
