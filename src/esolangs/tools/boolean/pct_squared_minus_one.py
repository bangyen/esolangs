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

Coverage: every table at ``n <= 2``, the sixteen two-input functions with
XOR and XNOR included.  At ``n == 3`` the solver separates only a minority
within its budget -- 2 of a 24-table sample -- and
:func:`pct_squared_minus_one` raises :class:`ValueError` rather than
returning a program for a table it could not separate, so a caller never
receives one that computes the wrong function.

Unlike the other parameterized generators, *which* command strings a setter
uses is solved per table rather than fixed by the language, so a bare
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
from itertools import product

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["pct_squared_minus_one"]

#: The accumulator is zeroed when it exceeds this, checked before each command.
_LIMIT = 3003

#: Affine multipliers a setter may realise: identity, negate, erase, double.
_A_VALS = (1, -1, 0, 2)

#: Additive offsets searched for each setter branch, smallest magnitude
#: first so the solver reaches a short program before a long one.  Widening
#: this past ``+/-8`` was measured: it bought no extra ``n == 3`` table and
#: cost roughly 50x on the ``n == 2`` sweep, because the assignment count
#: grows as ``len(_OPTIONS) ** (2 * n)``.
_B_VALS = (0, -2, -3, 2, 3, -4, -5, -6, -7, -8)

#: Setter assignments the solver will try before giving up on a table.
_BUDGET = 2_000_000

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


def _row_bits(row: int, n: int) -> list[int]:
    """Return ``row``'s input bits, most significant first."""
    return [(row >> (n - 1 - i)) & 1 for i in range(n)]


def _pad_pair(zero: str, one: str) -> tuple[str, str] | None:
    """Pad two setter branches to equal width, preserving each one's value.

    A program whose length depends on its inputs leaks them through
    ``len()``, so both branches of a setter must be the same width.  The pad
    is ``pp``: two negations, which the interpreter *executes* and which
    compose to the identity, so a later pass stripping characters the
    language merely ignores could not reintroduce the leak.  Only an even
    shortfall can be padded this way; an odd one returns ``None`` and the
    caller moves on to a different offset.
    """
    gap = len(one) - len(zero)
    if gap % 2:
        return None
    if gap > 0:
        return zero + "p" * gap, one
    return zero, one + "p" * (-gap)


def _setter_options() -> list[str]:
    """Return every setter branch the solver may use, shortest first."""
    seen: dict[str, None] = {}
    for a in _A_VALS:
        for b in _B_VALS:
            code = _affine_code(a, b)
            if code is not None:
                seen.setdefault(code, None)
    return sorted(seen, key=len)


_OPTIONS = _setter_options()


@cache
def _tail_for(one_value: int, zero_value: int) -> str | None:
    """Return a tail printing ``1`` from ``one_value`` and ``0`` from ``zero_value``.

    ``l`` prints the accumulator in decimal and applies the over-3003 reset
    first, so the tail has to land the one-class on exactly 1 and the
    zero-class on 0 -- or above 3003, which the reset folds onto 0.

    Three shapes are tried, cheapest first.  A bare translation moves both
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
                if _apply(one_value, body) == 1 and _apply(zero_value, body) == 0:
                    return body + "l"
    return None


def _solve(truth_table: str, n: int) -> tuple[list[tuple[str, str]], str] | None:
    """Search for setters and a tail realising ``truth_table``.

    Each input gets one affine map per bit value; composing them left to
    right makes the accumulator a product-weighted function of the bits.  A
    table is realisable when every row answering 1 reaches one accumulator
    value and every row answering 0 reaches another.

    The search is capped: the assignment count grows as
    ``len(_OPTIONS) ** (2 * n)``, so an uncapped sweep at ``n >= 3`` spends
    minutes proving a negative.  Exhausting the budget returns ``None``, the
    same as a genuine exhaustion -- the caller raises either way, so a table
    is never given a program that computes the wrong function.
    """
    rows = range(2**n)
    budget = _BUDGET
    for combo in product(product(_OPTIONS, repeat=2), repeat=n):
        budget -= 1
        if budget < 0:
            return None
        padded: list[tuple[str, str]] = []
        for zero_code, one_code in combo:
            pair = _pad_pair(zero_code, one_code)
            if pair is None:
                break
            padded.append(pair)
        else:
            values = []
            for row in rows:
                acc = 0
                for k, bit in enumerate(_row_bits(row, n)):
                    acc = _apply(acc, padded[k][bit])
                values.append(acc)
            ones = {values[r] for r in rows if truth_table[r] == "1"}
            zeros = {values[r] for r in rows if truth_table[r] == "0"}
            if len(ones) > 1 or len(zeros) > 1 or (ones & zeros):
                continue
            # A constant table leaves one class empty; any value distinct
            # from the live class serves as the absent one.
            one_value = next(iter(ones)) if ones else next(iter(zeros)) + 1
            zero_value = next(iter(zeros)) if zeros else next(iter(ones)) - 1
            tail = _tail_for(one_value, zero_value)
            if tail is not None:
                return padded, tail
    return None


def pct_squared_minus_one(truth_table: str) -> str:
    """Build a %^2^-1 template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    %^2^-1 has no usable branch -- ``t`` only ever jumps to position 0 -- so
    this generator computes the answer arithmetically instead of routing a
    decision tree.  Each ``{Xk:<zero>|<one>}`` placeholder holds the two
    equal-width command strings that input may contribute; they compose as
    affine maps whose product weighting is nonlinear in the bits, and the
    shared tail moves the one-class to 1 and the zero-class to 0 before a
    single ``l`` prints it in decimal.

    Raises :class:`ValueError` when the solver cannot separate the table
    within its search budget, rather than emitting a program that would
    compute the wrong function.
    """
    n = _validate_truth_table(truth_table)
    solved = _solve(truth_table, n)
    if solved is None:
        raise ValueError(f"no %^2^-1 separation found for truth table {truth_table!r}")
    setters, tail = solved
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
