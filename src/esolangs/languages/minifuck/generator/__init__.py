"""Minifuck Boolean program generator: input substitution into a positional template.

Races the positional decoder against byte-accumulator forms.
Two-residual candidates keep their state in output bit 7; ignored setters
write beyond the output byte.  A positional strip supplies the size floor.
The simulator laws are pinned differentially against the interpreter.

Size:
    Parity is O(n) through the two-residual diagram, other tables O(T).
    n=16 parity: 440 chars, n=10 random 1847: 40,501 chars.

Decisions:
    Seeded n=16 affine (100 tables): 488-764 characters against
    815-315,474 positional.  An affine table's residuals are the function
    or its complement, so :func:`two_state` always fits it; the parity
    columns race only under an explicit width.
    :func:`two_state` allows at most two residuals per level, :func:`stored`
    each residual once within the positional length.  Where they fit,
    :func:`two_state` saves 95-100% (n=8-16) and :func:`stored` 20-98% (and/or
    from n=10, parity from n=12, symmetric tables from n=14).
    :func:`two_state` labels each level's residuals so no level toggles and
    reads a minority at input 1 through ``[<[x<`` (no table swaps the setter
    pair, no header): n=8 AND 10,158 -> 309 chars, NAND 10,163 -> 312, OR
    488 -> 281, NOR 491 -> 278.
"""

import re
from collections.abc import Callable
from functools import cache, partial
from itertools import pairwise
from math import isqrt
from typing import Any, NamedTuple

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _parity_bias,
    _validate_shape,
    _validate_truth_table,
    essential_inputs,
    grid_width,
    mark_runs,
    read_at,
    same_up_to_wrapping,
    unmark,
)
from esolangs.generation.token_balance import CELL_ASPECT, balanced_token_width
from esolangs.generation.wrap import (
    _MINIFUCK_COMMAND,
    _RUN,
    _minifuck,
    balance_score,
    wrap_program,
)
from esolangs.languages.minifuck.generator.mux import (
    _MUX_MIN_ARITY,
    _canonical_endgame,
    _mux,
    _mux_lookup,
)
from esolangs.languages.minifuck.generator.pool import (
    _BASE,
    _embed,
)
from esolangs.languages.minifuck.generator.sim import (
    _MINIFUCK_INPUT,
    PAIR,
    _clamp,
)
from esolangs.languages.minifuck.generator.states import two_state
from esolangs.languages.minifuck.generator.stored import stored
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape

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
_INERT = "".join(
    (
        "[[",  # walk right twice, setting the two cells the guard clears
        "<<",  # walk back to cell 0
        "[",  # clear cell 1 (and cell 2 on the skip), skipping into the run
        _MINIFUCK_INPUT,  # the ignored input's own two-character run
        "<",  # step home to cell 0
    )
)


class _Reduced(NamedTuple):
    """A table with its ignored inputs removed."""

    first: int  # leading ignored inputs
    table: str  # inner table over the essential inputs
    kept: list[int]  # essential inputs
    gaps: tuple[int, ...]  # ignored inputs between consecutive essential ones
    after: int  # trailing ignored inputs


def _reduce(truth_table: str, n: int) -> _Reduced | None:
    """Drop ignored inputs; ``None`` when every input is essential.

    The caller puts an inert block in front for each leading ignored input
    and a run after the print for each trailing one.  An ignored input
    between two essential ones replaces a lookup pad step (``gaps``),
    extending the pad when fresh cells are needed.
    """
    essential = essential_inputs(truth_table, n)
    if len(essential) == n:
        return None
    first = essential[0] if essential else 0
    after = n - 1 - essential[-1] if essential else n
    gaps = tuple(b - a - 1 for a, b in pairwise(essential))
    return _Reduced(first, read_at(truth_table, essential, n), essential, gaps, after)


@cache
def _solve(truth_table: str) -> str:
    """Build the positional Minifuck template for a truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Runs become ``[<`` for a one and
    ``xx`` for a zero.  The program embeds each input once, computes past
    the pool, relays the answer into the *pointer*, and prints one digit.
    Closed-form displacement laws, pinned against the interpreter; cached.
    """
    n = _validate_shape(truth_table)
    reduced = _reduce(truth_table, n)
    if reduced is not None:
        return _solve_reduced(reduced)
    if n < _MUX_MIN_ARITY:
        # Nullary and unary tables use the embed's named standing column.
        degenerate = _degenerate(truth_table, n)
        if degenerate is None:  # pragma: no cover - nullary/unary column rule
            raise ValueError(
                f"the Minifuck boolean generator could not build {truth_table!r}"
            )
        return degenerate
    return _mux(truth_table, n)


def _solve_reduced(reduced: _Reduced) -> str:
    """Solve the inner table, then add the ignored inputs back as inert text.

    An interior ignored input replaces a lookup pad's last step; fresh
    padding grows only when the ignored run needs it.  Ten seeded n=8 tables
    ignoring input 6 average 5,129.8 characters against 10,159.1 without the
    reduction (49.5% smaller, seed 6072026).
    """
    first, inner_table, kept, gaps, after = reduced
    if any(gaps):
        inner = _mux_lookup(inner_table, len(kept), gaps=gaps)
    else:
        inner = _solve(inner_table)
    return _INERT * first + inner + _MINIFUCK_INPUT * after


def _overflow_score(program: str, width: int) -> tuple[int, int]:
    """Rank width-budgeted candidates: line overflow first, length second."""
    return max(0, grid_width(program) - width), len(program)


def minifuck(truth_table: str, width: int | None = None) -> str:
    """Build a Minifuck template; ``width`` set: least overflow, then smallest.

    Defaults retain ``(xx, [<)`` setters; narrow columns use ``(x, [)``.
    """
    n = _validate_truth_table(truth_table)
    natural = _solve(truth_table)
    positional = _lookup_layout(truth_table, n, natural, width)
    if width is None:
        return _race_states(truth_table, n, positional, width)
    mask = _affine_mask(truth_table)
    if mask is None:
        return _race_states(truth_table, n, positional, width)
    shared = _parity_columns(n, int(truth_table[0]), mask=mask, paired=True)
    shared = _wrap_template(shared, n, width)
    if grid_width(shared) > width:
        shared = _parity_columns(n, int(truth_table[0]), mask=mask)
    if len(shared) > len(positional):
        return positional
    return min(positional, shared, key=partial(_overflow_score, width=width))


def _race_states(truth_table: str, n: int, positional: str, width: int | None) -> str:
    """Pick the best of the positional layout and the byte-state forms."""
    others = [
        candidate
        for candidate in (two_state(truth_table), stored(truth_table, len(positional)))
        if candidate is not None
    ]
    if width is None:
        return min([positional, *others], key=len)
    candidates = [positional] + [
        wrapped
        for candidate in others
        if len(wrapped := _wrap_template(candidate, n, width)) <= len(positional)
    ]
    return min(candidates, key=partial(_overflow_score, width=width))


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
    if width is None:
        return natural
    wrapped = _wrap_template(natural, n, width)
    if grid_width(wrapped) <= width:
        return wrapped
    if width < 4 and _parity_bias(table) is not None:
        return _parity_columns(n, int(table[0]))
    narrow = _narrow(table, n)
    narrow = _wrap_template(narrow, n, width)
    return narrow if grid_width(narrow) < grid_width(wrapped) else wrapped


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
    if reduced is None or not reduced.kept:
        return _paired(truth_table, n)
    first, inner_table, kept, gaps, after = reduced
    inner = _paired(inner_table, len(kept), gaps)
    return _INERT * first + inner + _MINIFUCK_INPUT * after


class _ParityEmitter:
    """Emit parity-column commands while tracking the tape model.

    ``[`` walks right and flips the landing cell (flipping the next cell
    too, and skipping an instruction, when it lands on zero); ``<`` walks
    left, staying at cell 0.  ``bits`` mirrors the cells and ``pointer``
    the head, so the caller can read each cell's parity back after the
    setters; ``parts`` collects the emitted program text.
    """

    def __init__(self, *, paired: bool) -> None:
        self.bits = [0] * 10
        self.pointer = 0
        self.parts = [] if paired else ["q"]

    def emit(self, command: str) -> None:
        self.parts.append(command)
        if command == "<":
            self.pointer = max(0, self.pointer - 1)
        else:
            self.pointer += 1
            self.bits[self.pointer] ^= 1
            if not self.bits[self.pointer]:
                self.bits[self.pointer + 1] ^= 1


def _parity_columns(
    n: int, complement: int, *, mask: int | None = None, paired: bool = False
) -> str:
    """Accumulate XOR in bit 7; unselected setters write cell 9 instead."""
    emitter = _ParityEmitter(paired=paired)
    emit = emitter.emit
    bits = emitter.bits
    parts = emitter.parts

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
    """The one setter pair, narrowed for the parity layout's inert q prefix."""
    return (("x", "[") if template.startswith("q\n") else PAIR,) * n


def _wrap_template(template: str, n: int, width: int) -> str:
    """Wrap a template with each two-character input run kept atomic."""
    marked = mark_runs(template, TEMPLATE_CHAR, (PAIR,) * n)
    return unmark(wrap_program(marked, "minifuck", width), TEMPLATE_CHAR, n)


def _tokens(program: str, n: int) -> list[str]:
    """Split a program into commands, each two-character input run one token."""
    marked = mark_runs(program.replace("\n", ""), TEMPLATE_CHAR, (PAIR,) * n)
    return re.findall(f"{_RUN}|{_MINIFUCK_COMMAND}", marked)


def _lookup_balance(table: str, default: str) -> str:
    """Balance ordinary and paired skip tokens, including the parity column."""
    n = _validate_truth_table(table)
    normal = _tokens(default, n)
    floor = max(map(len, normal))
    width = balanced_token_width(normal, minimum=floor)
    candidates = [
        default,
        _lookup_layout(table, n, default, width),
        _lookup_layout(table, n, default, 1),
    ]
    parity = _parity_bias(table) is not None
    lower = 4 if parity else 1
    if lower < floor:
        # Below the ordinary token floor, paired tokens win throughout the
        # regime exactly when their own floor is smaller; otherwise the
        # generator retains the ordinary tokens throughout it.
        narrow = _tokens(_lookup_layout(table, n, default, lower), n)
        width = balanced_token_width(narrow, minimum=lower, maximum=floor - 1)
        candidates.append(_lookup_layout(table, n, default, width))
    # No inert padding: it adds length and never shrinks the rendered side.
    return min(candidates, key=balance_score)


def _shared_form(shared: str, n: int, *, sqrt_wrap: bool) -> str:
    """Wrap a shared-residual template square-ish."""
    tokens = _tokens(shared, n)
    # A unary tape walk can contain O(T) tokens. A square-root wrap gives a
    # square-ish fold without enumerating token-fit widths.
    width = (
        max(isqrt(CELL_ASPECT * len(shared)) + 1, max(map(len, tokens)))
        if sqrt_wrap
        else balanced_token_width(tokens, minimum=max(map(len, tokens)))
    )
    return _wrap_template(shared, n, width)


def _balance(table: str, default: str) -> str:
    """Compare byte accumulators with the positional balance floor."""
    n = len(table).bit_length() - 1
    positional = _lookup_balance(table, _solve(table))
    mask = _affine_mask(table)
    forms: list[str] = []
    if mask is None:
        if (two := two_state(table)) is not None:
            forms.append(_shared_form(two, n, sqrt_wrap=False))
        if (kept := stored(table, len(positional))) is not None:
            forms.append(_shared_form(kept, n, sqrt_wrap=True))
    else:
        parity = _parity_columns(n, int(table[0]), mask=mask, paired=True)
        forms.append(_shared_form(parity, n, sqrt_wrap=False))
    candidates = [positional]
    if len(default) <= len(positional):
        candidates.append(default)
    candidates.extend(shared for shared in forms if len(shared) <= len(positional))
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
    "minifuck",
    category="tape_based",
    size_bound=lambda n: 70 * 2**n,
    boolean=minifuck,
    same_layout=_same_layout,
    # Indexed strip or byte-state accumulator.
    shape=Shape.LOOKUP,
    contract=BooleanContract(),
    # ``[`` skips the character after it.
    wrap=_minifuck,
    wrap_multiline=True,
    balance=_balance,
    example=Example(setters=minifuck_setters),
)
