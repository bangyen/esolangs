"""Boolean program generator for Modulous.

A string literal has no subtrees to fold or share.
"""

import re
from itertools import pairwise

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    grid_width,
    input_weights,
)
from esolangs.generation.token_balance import (
    balanced_token_width,
    near_even_counts,
    run_widths,
)
from esolangs.generation.wrap import (
    _BRACKET_LITERAL,
    _bracket_literal,
    balance_score,
    wrap_space_delimited,
)
from esolangs.registry._language import Language, Shape

# Characters around the table in its literal push: ``[PSH STR "`` opens it
# (10 chars) and ``"]`` closes the literal (2 chars).
_TABLE_PUSH_OVERHEAD = len('[PSH STR ""]')

# Token lengths of the chunk-boundary window ``[ PSH STR "<chunk>"] [ PSH STR``
# with the chunk itself zeroed, so slice sums over it measure only the fixed
# push syntax straddling a chunk boundary.
_CHUNK_BOUNDARY_FIXED = [1, 3, 3, 0, 1, 3, 3]

# A chunk token ``"<chunk>"]`` is the chunk plus quote, quote, bracket.
_CHUNK_TOKEN_EXTRA = 3

# Estimated fixed characters per table chunk: the ``[PSH STR "`` / ``"]`` push
# syntax plus its separators -- the per-chunk term of the length proxy scored
# in the chunked search below.
_CHUNK_PUSH_OVERHEAD = 14

# Narrowest chunk width the search considers: ``[ PSH STR`` is 9 characters and
# needs a row of its own, so narrower chunks cannot use the two-rows-per-push
# layout the row estimate assumes.
_MIN_CHUNK_WIDTH = 6

# A bracketed string literal with its closer, a mnemonic, a number or a glyph.
_TOKEN = re.compile(r'"[^"]*"\]|[A-Z]+|\d+|\S')


def modulous(truth_table: str, width: int | None = None) -> str:
    """Return a Modulous table lookup; ``width`` folds command whitespace.

    Literals are chunked to fit; each quoted chunk keeps its closing bracket.
    """
    n = _validate_truth_table(truth_table)
    # ``PSH STR`` pushes the characters in reverse, so the leftmost entry is on
    # top and discarding ``index`` of them uncovers ``truth_table[index]`` --
    # the row index read MSB first, which is what the weights below build.  A
    # pushed zero is the counter; an ignored input is read and popped, and the
    # table is indexed by the rest.  Letting the first read be the counter
    # saves 6.8% at n=6, 4.1% at n=8, 1.9% at n=10, under the 10% bar.
    weights, truth_table = input_weights(truth_table, n)
    reads = ["[PSH INT 0]"]
    for weight in weights:
        if weight:
            reads.append(f"[INP INT][JMP F 4 IF 0][POP][ADD {weight}][JMP F 2][POP]")
        else:
            reads.append("[INP INT][POP]")
    # ``SWP``/``POP`` discards the entry *under* the counter, which is what
    # keeps the counter reachable: nothing but the top two cells is.
    walk = "[JMP F 5 IF 0][SUB 1][SWP][POP][JMP B 4][POP][PRT][END]"
    program = f'[PSH STR "{truth_table}"]{"".join(reads)}{walk}'
    if width is None or width <= 0:
        return program
    wrapped = _bracket_literal(program, width)
    if grid_width(wrapped) <= width:
        return wrapped
    # Push chunks from last to first: each string itself pushes in reverse.
    # All jumps follow the prologue and are relative, so its length is free.
    chunk = max(1, width - 3)
    starts = range(0, len(truth_table), chunk)
    prologue = (
        "".join(f"[PSH INT {_ASCII_ZERO + int(bit)}]" for bit in reversed(truth_table))
        if width < 4
        else "".join(
            f'[PSH STR "{truth_table[start : start + chunk]}"]'
            for start in reversed(starts)
        )
    )
    tokens = _TOKEN.findall(prologue + "".join(reads) + walk)
    return wrap_space_delimited(" ".join(tokens), width)


def _height(parts: list[int], columns: int) -> int:
    """Greedy single-space wrap row count for token lengths."""
    rows, used = 1, 0
    for length in parts:
        if used and used + 1 + length > columns:
            rows += 1
            used = length
        else:
            used += length + bool(used)
    return rows


def _best_chunked_columns(
    table: str, suffix_lengths: list[int], suffix_fits: set[int]
) -> int | None:
    """Return the best column width from the chunked-table search, if any.

    Splits the table literal into ``count`` ``[PSH STR "…"]`` pushes and scans
    chunk widths, counting rows at ``chunk width + 3`` columns -- the exact fit
    of a full chunk token -- as the greedy wrap of the first chunk's boundary
    window (``[ PSH STR "<chunk>"] [ PSH STR``), plus one row for the second
    push's tail and two rows per remaining push, plus the greedy wrap of the
    instruction suffix.  Only chunk widths where a greedy row count can change
    are visited: widths where a suffix token run exactly fills the column
    budget, and widths where the boundary window rewraps, for chunk counts
    near the divisors of ``size - 1``.  Each visited interval scores
    ``(|columns - rows|, size + 14 * count, columns)`` -- squareness first,
    then an estimated program length (table characters plus push syntax per
    chunk), then width -- and the winning width is the squarest point of its
    interval.
    """
    size = len(table)

    # Widths of the push syntax around a chunk boundary: every contiguous run
    # of the boundary template straddling the (zeroed) chunk token.
    boundary_fits = {
        sum(_CHUNK_BOUNDARY_FIXED[start:stop]) + stop - start - 1
        for start in range(4)
        for stop in range(4, 8)
    }
    quotients = near_even_counts(size)

    best: tuple[int, int, int] | None = None
    for count in quotients:
        # ``count`` pushes need chunks of at least ``size / count`` characters;
        # the bounds keep the final chunk non-empty and short of a full chunk.
        lower = max(_MIN_CHUNK_WIDTH, (size + count - 1) // count)
        upper = min(size - 1, (size - 1) // (count - 1))
        if lower > upper:
            continue
        events = {lower, upper + 1}
        events.update(fit for fit in suffix_fits if lower < fit <= upper)
        events.update(
            point
            for extra in boundary_fits
            if lower < (point := (size + extra + count - 1) // count) <= upper
        )
        boundaries = sorted(events)
        for start, stop in pairwise(boundaries):
            partial = size - (count - 1) * start
            # The boundary window with the partial chunk filled in.
            rows = (
                _height(
                    [1, 3, 3, partial + _CHUNK_TOKEN_EXTRA, 1, 3, 3],
                    start + _CHUNK_TOKEN_EXTRA,
                )
                + 2 * count
                - 3
                + _height(suffix_lengths, start + _CHUNK_TOKEN_EXTRA)
            )
            # Squarest width inside this event interval.
            columns = min(max(rows, start + _CHUNK_TOKEN_EXTRA), stop + 2)
            score = (
                abs(columns - rows),
                size + _CHUNK_PUSH_OVERHEAD * count,
                columns,
            )
            if best is None or score < best:
                best = score
    return best[2] if best is not None else None


def _balance(table: str, default: str) -> str:
    """Return the squarest rendering of the table lookup program.

    Renders ``modulous(table, width)`` at a family of candidate widths -- plus
    the unwrapped ``default`` -- and keeps the one minimizing ``balance_score``
    (row/column imbalance, then program length, then width):

    * whole bracket atoms (``[PSH STR "…"]`` stays intact), at the optimal
      greedy width above the longest atom;
    * the fine token stream rewrapped at narrow widths 1 through 8;
    * the whole table as one literal chunk, at the optimal width between
      ``size + 3`` and the longest atom;
    * the chunked-table search in ``_best_chunked_columns``.
    """
    atoms = re.findall(_BRACKET_LITERAL, default)
    floor = max(map(len, atoms))
    width = balanced_token_width(atoms, minimum=floor)
    candidates = [default, modulous(table, width)]
    numeric = modulous(table, 1).split()
    width = balanced_token_width(numeric, " ", maximum=3)
    candidates.append(modulous(table, width))
    # Below nine columns the three-word push prefix cannot share a row.
    candidates.extend(modulous(table, width) for width in range(4, 9))
    size = len(table)
    whole = modulous(table, size + 3).split()
    width = balanced_token_width(whole, " ", minimum=size + 3, maximum=floor - 1)
    candidates.append(modulous(table, width))
    # Skip the ``[PSH STR "`` prologue, the table, and the ``"]`` closer: the
    # rest is the instruction suffix whose rows the chunked search packs.
    suffix = _TOKEN.findall(default[size + _TABLE_PUSH_OVERHEAD :])
    lengths = list(map(len, suffix))
    # A suffix token run exactly fills a column budget of ``span``;
    # subtract the chunk-to-column offset to get the chunk width.
    fits = {span - _CHUNK_TOKEN_EXTRA for span in run_widths(lengths)}
    columns = _best_chunked_columns(table, lengths, fits)
    if columns is not None:
        candidates.append(modulous(table, columns))
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Modulous",
    "modulous",
    category="stack_based",
    random=True,
    boolean=modulous,
    # Not a tree: pops a ``PSH STR`` table down to the indexed character.
    shape=Shape.LOOKUP,
    balance=_balance,
)
