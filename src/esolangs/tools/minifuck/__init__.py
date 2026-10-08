"""Build Minifuck Boolean templates by input substitution.

Each input is embedded once at equal width; every row is verified with
the joint simulator and an unverified program raises.  The simulator laws
are pinned differentially against the interpreter.

The strip is positional: the pointer lands on a control cell by weighted
displacement, so every row owns a cell and a constant half or repeat has no
subtree to fold or share.
"""

import re
from functools import cache
from itertools import pairwise

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_shape,
    _validate_truth_table,
    essential_inputs,
    mark_runs,
    read_at,
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


def _kept_inputs(essential: list[int]) -> list[int]:
    """Return the essential inputs plus the ignored ones a pad cannot absorb.

    An ignored input between two kept ones, with two essential inputs after
    it, replaces a pad step (see :data:`_GAP_BLOCK`); only a pad of three or
    more steps ends with both cells right of the pointer zero, so the last
    pad takes none.  The others stay inputs of the lookup.  Leading and
    trailing ones are dropped by the caller.
    """
    kept = list(essential)
    for p in range(essential[0] + 1, essential[-1]):
        if p in essential:
            continue
        later = [e for e in essential if e > p + 1]
        if p - 1 in kept and p + 1 in essential and later:
            continue
        kept.append(p)
    return sorted(kept)


def _reduce(
    truth_table: str, n: int
) -> tuple[int, str, list[int], tuple[int, ...], int] | None:
    """Return (leading ignored, inner table, kept inputs, gaps, trailing ignored).

    ``None`` when every input is essential.  A table that ignores inputs is a
    smaller table wearing extra ones: the caller puts an inert block in front
    for each leading ignored input and a run after the print for each
    trailing one.  An ignored input between two essential ones replaces a
    lookup pad's last step where one fits (``gaps``).
    """
    essential = essential_inputs(truth_table, n)
    if len(essential) == n:
        return None
    first = essential[0] if essential else 0
    after = n - 1 - essential[-1] if essential else n
    kept = _kept_inputs(essential) if essential else essential
    gaps = tuple(b - a - 1 for a, b in pairwise(kept))
    return first, read_at(truth_table, kept, n), kept, gaps, after


@cache
def _solve(truth_table: str) -> str:
    """Build a Minifuck template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Runs become ``[<`` for a one and
    ``xx`` for a zero.  The program embeds each input once, computes past
    the pool, relays the answer into the *pointer*, and prints one digit;
    every emission is tracked against all rows by
    :mod:`esolangs.tools.minifuck.sim` and :class:`ValueError` is raised
    otherwise.  Cached; no route enumerates candidates.

    Ignored inputs are dropped (mean emitted characters, 10 seeded tables per
    cell, against the lookup with every input essential): one ignored input
    -49% at n=8 (-44% at n=5), two -74% (-65%).  The exception is an ignored
    input immediately before the last essential one: no pad can absorb it,
    so it stays an input (0%, never larger).
    """
    n = _validate_shape(truth_table)

    # A table that ignores inputs is a smaller table wearing extra ones: solve
    # it there, put an inert block in front for each ignored input before the
    # essential ones and a run after the print for each one past them.  An
    # ignored input between two essential ones replaces a lookup pad's last
    # step where one fits; otherwise the full-arity mux, which embeds every
    # slot in order, takes the table.
    reduced = _reduce(truth_table, n)
    if reduced is not None:
        first, inner_table, kept, gaps, after = reduced
        if kept == essential_inputs(truth_table, n) and not any(gaps):
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

    :func:`_solve` plus the arity check: ``_solve`` accepts a nullary table
    while recursing (six such calls building the 276 tables up to three
    inputs), but the API refuses it.  Narrow layouts pair fresh walks with
    comments so skip chains no longer bind the padding into one long line; they
    drop ignored inputs as :func:`_solve` does (width 1/8, 10 seeded tables per
    cell, n=6: one ignored input -47%, two -63%).
    """
    n = _validate_truth_table(truth_table)
    natural = _solve(truth_table)
    if width is None or width <= 0:
        return natural
    wrapped = _wrap_template(natural, n, width)
    if max(map(len, wrapped.splitlines())) <= width:
        return wrapped
    if width < 4 and all(
        int(bit) == ((row.bit_count() ^ int(truth_table[0])) & 1)
        for row, bit in enumerate(truth_table)
    ):
        return _parity_columns(n, int(truth_table[0]))
    narrow = _narrow(truth_table, n)
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


def _parity_columns(n: int, complement: int) -> str:
    """Toggle output bit 7 with each input; every skip absorbs only LF."""
    bits = [0] * 10
    pointer = 0
    parts = ["q"]

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

    for _ in range(n):
        for _ in range(6):
            emit("[")
        parts.append(TEMPLATE_CHAR)
        # Either input ends at 6 or 7; clamping seven left steps returns to 0.
        for _ in range(7):
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
    return "\n".join(parts)


def minifuck_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Recognize the parity layout's inert q prefix; retain legacy two-cell bits."""
    return (("x", "[") if template.startswith("q\n") else PAIR,) * n


def _wrap_template(template: str, n: int, width: int) -> str:
    """Wrap a template with each two-character input run kept atomic."""
    from esolangs.tools.wrap import wrap_program

    marked = mark_runs(template, TEMPLATE_CHAR, (PAIR,) * n)
    return unmark(wrap_program(marked, "minifuck", width), TEMPLATE_CHAR, n)


def _balance(table: str, default: str) -> str:
    """Balance ordinary and paired skip tokens, including the parity column."""
    n = _validate_truth_table(table)

    def tokens(program: str) -> list[str]:
        marked = mark_runs(program.replace("\n", ""), TEMPLATE_CHAR, (PAIR,) * n)
        return re.findall(f"{_RUN}|{_MINIFUCK_COMMAND}", marked)

    normal = tokens(default)
    floor = max(map(len, normal))
    width = balanced_token_width(normal, minimum=floor)
    candidates = [default, minifuck(table, width), minifuck(table, 1)]
    parity = all(
        int(bit) == ((row.bit_count() ^ int(table[0])) & 1)
        for row, bit in enumerate(table)
    )
    lower = 4 if parity else 1
    if lower < floor:
        # Below the ordinary token floor, paired tokens win throughout the
        # regime exactly when their own floor is smaller; otherwise the
        # generator retains the ordinary tokens throughout it.
        narrow = tokens(minifuck(table, lower))
        width = balanced_token_width(narrow, minimum=lower, maximum=floor - 1)
        candidates.append(minifuck(table, width))
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Minifuck",
    "tape_based.minifuck",
    boolean=minifuck,
    contract=BooleanContract(),
    # ``[`` skips the character after it.
    wrap=_minifuck,
    balance=_balance,
    example=Example(setters=minifuck_setters),
)
