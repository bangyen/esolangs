"""Build Minifuck Boolean templates by input substitution.

Affine candidates keep their two residual classes in output bit 7; ignored
setters write beyond the output byte. A positional strip supplies the size floor.
The simulator laws are pinned differentially against the interpreter.
"""

import re
from collections.abc import Callable
from functools import cache
from itertools import pairwise
from typing import Any

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_shape,
    _validate_truth_table,
    essential_inputs,
    mark_runs,
    read_at,
    same_up_to_wrapping,
    unmark,
)
from esolangs.tools.minifuck.mux import (
    _MUX_MIN_ARITY,
    _canonical_endgame,
    _mux,
    _mux_lookup,
)
from esolangs.tools.minifuck.pool import (
    _BASE,
    _embed,
)
from esolangs.tools.minifuck.sim import (
    _MINIFUCK_INPUT,
    PAIR,
    _clamp,
)
from esolangs.tools.token_balance import balanced_token_width
from esolangs.tools.wrap import _MINIFUCK_COMMAND, _RUN, _minifuck, balance_score

__all__ = ["minifuck"]


def _degenerate(truth_table: str, n: int) -> str | None:
    """Build a table depending on at most one input, without the ladder.

    A constant, projection or negated projection already stands as a
    column: cell 16 prints ``b0``, cell 19 ``~b1``, a constant at 16
    (nullary) or 17.  A table with ``k`` essential inputs is a ``k``-input
    problem, so four of the fourteen three-input orbits land here.  Later
    projections decline to :func:`_mux`.
    """
    essential = essential_inputs(truth_table, n)
    if len(essential) > 1:
        return None
    if not essential:
        acc = _BASE if n == 0 else _BASE + 1
        direct = truth_table[0] == ("1" if n == 0 else "0")
    elif essential[0] == 0:
        acc = _BASE
        direct = truth_table[0] == "0"
    elif essential[0] == 1:
        acc = _BASE + 3
        direct = truth_table[0] == "1"
    else:
        return None

    base = _embed(n)
    _clamp(base)
    _canonical_endgame(base, acc, direct=direct)
    if base.printed() != list(truth_table):  # pragma: no cover - the law is exact
        raise AssertionError("the degenerate rule printed the wrong column")
    return base.template()


#: An ignored input's run between two fixed halves: either fill walks the
#: fresh tape back to fresh -- zero cells, pointer 0, no skip pending -- so a
#: block in front of a program leaves it the start it was verified from.
_INERT = "[[<<[" + _MINIFUCK_INPUT + "<"


def _reduce(
    truth_table: str, n: int
) -> tuple[int, str, list[int], tuple[int, ...], int] | None:
    """Return (leading ignored, inner table, essential inputs, gaps, trailing ignored).

    ``None`` when every input is essential.  A table that ignores inputs is a
    smaller table wearing extra ones: the caller puts an inert block in front
    for each leading ignored input and a run after the print for each
    trailing one.  An ignored input between two essential ones replaces a
    lookup pad step (``gaps``), extending the pad when fresh cells are needed.
    """
    essential = essential_inputs(truth_table, n)
    if len(essential) == n:
        return None
    first = essential[0] if essential else 0
    after = n - 1 - essential[-1] if essential else n
    gaps = tuple(b - a - 1 for a, b in pairwise(essential))
    return first, read_at(truth_table, essential, n), essential, gaps, after


@cache
def _solve(truth_table: str) -> str:
    """Build a Minifuck template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Runs become ``[<`` for a one and
    ``xx`` for a zero.  The program embeds each input once, computes past
    the pool, relays the answer into the *pointer*, and prints one digit.
    The strip uses closed-form displacement laws, pinned against the
    interpreter. Cached; no route searches.

    Ignored inputs leave the index; an interior run extends its pad enough to
    cross the preceding setter. Ten seeded n=8 tables ignoring input 6 average
    5,209.8 characters against 10,239.1 before (49.1% smaller, seed 6072026).
    """
    n = _validate_shape(truth_table)

    # A table that ignores inputs is a smaller table wearing extra ones: solve
    # it there, put an inert block in front for each ignored input before the
    # essential ones and a run after the print for each one past them.  An
    # ignored input between two essential ones replaces a lookup pad's last
    # step; fresh padding grows only when the ignored run needs it.
    reduced = _reduce(truth_table, n)
    if reduced is not None:
        first, inner_table, kept, gaps, after = reduced
        if not any(gaps):
            inner = _solve(inner_table)
        else:
            inner = _mux_lookup(inner_table, len(kept), gaps=gaps)
        return _INERT * first + inner + _MINIFUCK_INPUT * after

    # The strip's crossover: the direct lookup is O(T) for every wider table.
    if n >= 5:
        return _mux_lookup(truth_table, n)

    # Nullary and unary inner solves use the embed's named standing column.
    if n < _MUX_MIN_ARITY:
        degenerate = _degenerate(truth_table, n)
        if degenerate is None:  # pragma: no cover - nullary/unary column rule
            raise ValueError(
                f"the Minifuck boolean generator could not build {truth_table!r}"
            )
        return degenerate

    return _mux(truth_table, n)


def minifuck(truth_table: str, width: int | None = None) -> str:
    """Build a Minifuck template for the given truth table.

    Compare the positional decoder with an affine byte accumulator. Defaults
    retain ``(xx, [<)`` setters; narrow columns use ``(x, [)``. All candidates
    consume inputs in order. Sixty-four seeded affine tables at n=16 average
    552.8 characters against 30,849.8 before (98.2% smaller, seed 32026).
    Non-affine layouts retain the positional construction.
    """
    n = _validate_truth_table(truth_table)
    natural = _solve(truth_table)
    mask = _affine_mask(truth_table)
    if mask is None:
        return _lookup_layout(truth_table, n, natural, width)
    shared = _parity_columns(n, int(truth_table[0]), mask=mask, paired=True)
    if width is None or width <= 0:
        return min(natural, shared, key=len)
    legacy = _lookup_layout(truth_table, n, natural, width)
    shared = _wrap_template(shared, n, width)
    if max(map(len, shared.splitlines())) > width:
        shared = _parity_columns(n, int(truth_table[0]), mask=mask)
    if len(shared) > len(legacy):
        return legacy
    return min(
        legacy,
        shared,
        key=lambda program: (
            max(0, max(map(len, program.splitlines())) - width),
            len(program),
        ),
    )


@cache
def _affine_mask(truth_table: str) -> int | None:
    """Return the XOR mask inferred from singleton rows, or None, in O(T)."""
    n = len(truth_table).bit_length() - 1
    bias = int(truth_table[0])
    mask = sum((int(truth_table[1 << bit]) ^ bias) << bit for bit in range(n))
    return (
        mask
        if all(
            int(bit) == (((row & mask).bit_count() & 1) ^ bias)
            for row, bit in enumerate(truth_table)
        )
        else None
    )


def _lookup_layout(table: str, n: int, natural: str, width: int | None) -> str:
    """Lay out the positional decoder, retaining its narrow parity floor."""
    if width is None or width <= 0:
        return natural
    wrapped = _wrap_template(natural, n, width)
    if max(map(len, wrapped.splitlines())) <= width:
        return wrapped
    if width < 4 and all(
        int(bit) == ((row.bit_count() ^ int(table[0])) & 1)
        for row, bit in enumerate(table)
    ):
        return _parity_columns(n, int(table[0]))
    narrow = _narrow(table, n)
    narrow = _wrap_template(narrow, n, width)
    return (
        narrow
        if max(map(len, narrow.splitlines())) < max(map(len, wrapped.splitlines()))
        else wrapped
    )


def _paired(truth_table: str, n: int, gaps: tuple[int, ...] = ()) -> str:
    """Return the paired lookup of an ``n``-input table (``n >= 1``)."""
    if n == 1:
        # The lookup requires two inputs: duplicate each leaf and fix its
        # second setter to zero, leaving the first as the sole named input.
        narrow = _mux_lookup("".join(bit * 2 for bit in truth_table), 2, paired=True)
        at = narrow.rindex(_MINIFUCK_INPUT)
        return narrow[:at] + PAIR[0] + narrow[at + len(PAIR[0]) :]
    return _mux_lookup(truth_table, n, paired=True, gaps=gaps)


def _narrow(truth_table: str, n: int) -> str:
    """Return the paired lookup, dropping ignored inputs as :func:`_solve` does."""
    reduced = _reduce(truth_table, n)
    if reduced is None or not reduced[2]:
        return _paired(truth_table, n)
    first, inner_table, kept, gaps, after = reduced
    inner = _paired(inner_table, len(kept), gaps)
    return _INERT * first + inner + _MINIFUCK_INPUT * after


def _parity_columns(
    n: int, complement: int, *, mask: int | None = None, paired: bool = False
) -> str:
    """Accumulate XOR in bit 7; unselected setters write cell 9 instead."""
    bits = [0] * 10
    pointer = 0
    parts = [] if paired else ["q"]

    def emit(command: str) -> None:
        nonlocal pointer
        parts.append(command)
        if command == "<":
            pointer = max(0, pointer - 1)
        else:
            pointer += 1
            bits[pointer] ^= 1
            if not bits[pointer]:
                bits[pointer + 1] ^= 1

    for i in range(n):
        stop = 6 if mask is None or mask & (1 << (n - 1 - i)) else 8
        for _ in range(stop):
            emit("[")
        parts.append(_MINIFUCK_INPUT if paired else TEMPLATE_CHAR)
        # A setter ends at stop or stop+1; the clamp returns either fill to 0.
        for _ in range(stop + 1):
            emit("<")
    for cell in range(1, 7):
        emit("[")
        if bits[cell] != int(cell in (2, 3)):
            emit("<")
            emit("[")
    if bits[7] != (complement ^ 1):
        emit("[")
        emit("<")
    parts.append(".")
    return ("x" if paired else "\n").join(parts)


def minifuck_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Recognize the parity layout's inert q prefix; retain legacy two-cell bits."""
    return (("x", "[") if template.startswith("q\n") else PAIR,) * n


def _wrap_template(template: str, n: int, width: int) -> str:
    """Wrap a template with each two-character input run kept atomic."""
    from esolangs.tools.wrap import wrap_program

    marked = mark_runs(template, TEMPLATE_CHAR, (PAIR,) * n)
    return unmark(wrap_program(marked, "minifuck", width), TEMPLATE_CHAR, n)


def _lookup_balance(table: str, default: str) -> str:
    """Balance ordinary and paired skip tokens, including the parity column."""
    n = _validate_truth_table(table)

    def tokens(program: str) -> list[str]:
        marked = mark_runs(program.replace("\n", ""), TEMPLATE_CHAR, (PAIR,) * n)
        return re.findall(f"{_RUN}|{_MINIFUCK_COMMAND}", marked)

    normal = tokens(default)
    floor = max(map(len, normal))
    width = balanced_token_width(normal, minimum=floor)
    candidates = [
        default,
        _lookup_layout(table, n, default, width),
        _lookup_layout(table, n, default, 1),
    ]
    parity = all(
        int(bit) == ((row.bit_count() ^ int(table[0])) & 1)
        for row, bit in enumerate(table)
    )
    lower = 4 if parity else 1
    if lower < floor:
        # Below the ordinary token floor, paired tokens win throughout the
        # regime exactly when their own floor is smaller; otherwise the
        # generator retains the ordinary tokens throughout it.
        narrow = tokens(_lookup_layout(table, n, default, lower))
        width = balanced_token_width(narrow, minimum=lower, maximum=floor - 1)
        candidates.append(_lookup_layout(table, n, default, width))
    best = min(candidates, key=balance_score)
    gaps = tuple(b - a - 1 for a, b in pairwise(essential_inputs(table, n)))
    if gaps and (gaps[-1] or max(gaps) > 1):
        # Dropping the penultimate selector gave 40x39 against the old square
        # at n=6. Comments after the last instruction recover the square.
        return min(best, _square_tail(best), key=balance_score)
    return best


def _square_tail(program: str) -> str:
    """Square a layout with inert whitespace after its final instruction."""
    rows = program.split("\n")
    width = max(map(len, rows))
    height = len(rows)
    return (
        program + "\n" * (width - height)
        if height < width
        else program + " " * (height - len(rows[-1]))
    )


def _balance(table: str, default: str) -> str:
    """Compare the affine accumulator with the positional balance floor."""
    legacy = _lookup_balance(table, _solve(table))
    mask = _affine_mask(table)
    if mask is None:
        return legacy
    n = len(table).bit_length() - 1
    shared = _parity_columns(n, int(table[0]), mask=mask, paired=True)
    marked = mark_runs(shared, TEMPLATE_CHAR, (PAIR,) * n)
    tokens = re.findall(f"{_RUN}|{_MINIFUCK_COMMAND}", marked)
    width = balanced_token_width(tokens, minimum=max(map(len, tokens)))
    shared = _wrap_template(shared, n, width)
    square = _square_tail(shared)
    candidates = [legacy]
    candidates.extend(
        candidate
        for candidate in (default, shared, square)
        if len(candidate) <= len(legacy)
    )
    return min(candidates, key=balance_score)


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Newlines absorb skips: compare the narrow layouts without them."""
    for width in (1, 4):
        narrow = str(layout(width))
        if narrow.startswith("q\n"):
            # Exact layouts were checked by the caller.
            continue
        if template.replace("\n", "") == narrow.replace("\n", ""):
            return True
    return same_up_to_wrapping(template, plain)


LANGUAGE = Language(
    "Minifuck",
    "tape_based.minifuck",
    size_bound=lambda n: 70 * 2**n,
    boolean=minifuck,
    same_layout=_same_layout,
    # Indexed strip or affine accumulator.
    shape=Shape.LOOKUP,
    contract=BooleanContract(),
    # ``[`` skips the character after it.
    wrap=_minifuck,
    balance=_balance,
    example=Example(setters=minifuck_setters),
)
