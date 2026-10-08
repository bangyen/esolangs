"""Linear Boolean-function generator for Packlang.

Packlang's ``Array`` starts every element at the element type's minimum, so
a truth table is a *painted array* rather than a decision tree.  One array
of 128 rows is enough: the inputs above the block index are read into a
block number, each block paints the array inside the ``If`` that selects
it, and the answer is a single index into it.

That is what fixes the per-row cost.  A row costs one ``INCR t(k);`` --
Packlang writes by counting, so there is no shorter statement -- and ``k``
is an offset inside the block, so its digits stop growing once the table
passes one block.  A block holding more ones than zeros is filled by a loop
and its zeros punched back out, so a constant table pays per *block*; an
all-zero block paints nothing, and a block equal to an earlier one is aliased
to it (:func:`_blocks` shrinks the block until repeats align).

The answer prints ``48 ^ t``; the opposite polarity was dropped: it cost
+3.19% (3-input total) and +2.60% (seeded 5-input sample).

The index is counted too: each input doubles what has been read and adds
its bit.  Doubling drains one register into its partner two counts at a
time, so the two alternate and no copy is ever needed.
"""

import re
from itertools import pairwise, product

from esolangs._dialects import PacklangLiterals
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    input_weights,
    subtree_ids,
)
from esolangs.tools.wrap import (
    _PACKLANG_LEXEME,
    _join_tokens,
    _packlang,
    balance_score,
    wrap_program,
)

__all__ = ["packlang"]

#: Inputs the array block spans.  It bounds the index digits every painted
#: row pays, and the rows a fill loop has to walk.  Essential as a cap: one
#: 512-row array (n=9) did not terminate in 30 s (Char index wraps).  The
#: value is flat: 5/6/8 differ from 7 by +1.2%/-1.2%/+2.7% at n=10 (random).
_BLOCK = 7

#: The smallest block :func:`_blocks` tries; below it index digits dominate.
_MIN_BLOCK = 4

#: Fills cheaper than this many writes are not worth the loop that fills.
#: Dropping fill+punch costs +2.4% at n=8 random but +66% (n=8, 80% ones)
#: and +125% (n=10, 90% ones).
_FILL_COST = 3

#: The package name shortens below this many columns.
_NAME_LEN = len("truthTable")

#: Where a run of statements folds.  Whitespace is not a Packlang token, so
#: a break costs one character per line rather than one per statement.
_WIDTH = 72


def packlang(
    truth_table: str, width: int | None = None, *, literal_policy: str = "decimal"
) -> str:
    """Build a linear-size Packlang program; narrow layouts floor at one token.

    The unused package name shortens below ten columns; keywords floor at seven.
    """
    literals = PacklangLiterals(literal_policy)
    weights, table = input_weights(truth_table, _validate_truth_table(truth_table))
    built = []
    for runs, block in product((False, True), _blocks(table)):
        program = _painted(table, weights, runs=runs, block=block)
        if literal_policy != "decimal":
            program = re.sub(
                r"\b\d+\b", lambda match: literals.emit(int(match[0])), program
            )
        if width is not None and width > 0:
            # The package is never named by its own body or the IO dependency.
            if width < _NAME_LEN:
                program = _short_name(program)
            program = wrap_program(program, "packlang", width)
        built.append(program)
    return min(built, key=len)


def _blocks(table: str) -> list[int]:
    """Return the block sizes (log2 rows) to build.

    :data:`_BLOCK`, plus each smaller one where two blocks are equal and can
    alias; a single block cannot, so repeats shorter than it were never
    shared.  Tiled tables: -16..-18% at n=7, -22..-35% at n=8 (12 seeded
    tables); random tables never offer one, so they cost nothing.
    """
    n = len(table).bit_length() - 1
    top = min(n, _BLOCK)
    if n <= _MIN_BLOCK:
        return [top]
    ids = subtree_ids(table)
    smaller = [
        low for low in range(_MIN_BLOCK, top) if len(set(ids[n - low])) < 1 << (n - low)
    ]
    return [top, *smaller]


def _short_name(program: str) -> str:
    return program.removesuffix("} truthTable;\n") + "} t;\n"


def _balance_form(program: str, minimum: int, maximum: int) -> str:
    """Balance statement fits and the affine interval of reduced indentation."""
    records = []
    events = {minimum, maximum + 1}
    for line in program.split("\n"):
        tokens = re.findall(_PACKLANG_LEXEME, line)
        indent = len(line) - len(line.lstrip())
        longest = max(map(len, tokens), default=0)
        records.append((line, tokens, indent, longest))
        events.update((len(line), longest, indent + longest))
        for start in range(len(tokens)):
            span = -1
            for token in tokens[start:]:
                span += len(token) + 1
                events.update((span, indent + span))
    boundaries = sorted(point for point in events if minimum <= point <= maximum + 1)
    candidates = []
    for start, stop in pairwise(boundaries):
        height = 0
        offsets = []
        for line, tokens, indent, longest in records:
            if len(line) <= start:
                height += 1
                continue
            padding = min(indent, max(0, start - longest))
            rows = _join_tokens(tokens, max(1, start - padding), " ").split("\n")
            height += len(rows)
            span = max(map(len, rows))
            if longest <= start < longest + indent:
                offsets.append(span - longest)
        candidates.append(start)
        # Height is fixed between fits. Only reduced indentation grows with
        # width, so its crossing of height is the other possible minimum.
        if offsets:
            candidates.append(min(max(height - max(offsets), start), stop - 1))
    return min((_packlang(program, width) for width in candidates), key=balance_score)


def balance_packlang(_table: str, default: str) -> str:
    """Compare token-fit layouts with the two package-name spellings."""
    short = _short_name(default)
    maximum = max(map(len, default.split("\n"))) - 1
    return min(
        default,
        _balance_form(default, _NAME_LEN, maximum),
        _balance_form(short, 1, _NAME_LEN - 1),
        key=balance_score,
    )


def _painted(
    painted: str, weights: list[int], *, runs: bool, block: int = _BLOCK
) -> str:
    """Return a program painting ``painted``'s ones into an array.

    ``painted`` indexes the inputs of nonzero weight; the rest are read and
    dropped.
    """
    n = len(painted).bit_length() - 1
    low = min(n, block)
    span = 1 << low
    blocks = 1 << (n - low)
    # The block number's reads end at its last essential input.
    essential = [at for at, weight in enumerate(weights) if weight]
    cut = essential[n - low - 1] + 1 if blocks > 1 else 0

    body: list[str] = []
    index = "i"
    if blocks > 1:
        picked, index = _counter("h", "g", weights[:cut])
        body += picked
    counted, low_index = _counter("i", "d", weights[cut:])
    body += counted

    filled = False
    # A block equal to an earlier one is remapped onto it: the index is
    # decremented to the first copy's number before any block tests it
    # (-38.5% at n=9, -62.0% at n=10 with two distinct blocks).
    ids = subtree_ids(painted)[n - low] if blocks > 1 else []
    first: dict[int, int] = {}
    remaps: list[str] = []
    painting: list[str] = []
    for number in range(blocks):
        rows = painted[number * span : (number + 1) * span]
        writes, fill = _writes(rows, runs=runs)
        if not writes:
            continue
        if blocks == 1:
            painting += writes
            filled = fill
            continue
        test = f"If !({index}^{number})Then{{"
        copy = first.setdefault(ids[number], number)
        if copy < number:
            alias = [test, *[f"DECR {index};"] * (number - copy), "}"]
            if sum(map(len, alias)) < sum(map(len, writes)) + len(test) + 1:
                remaps += alias
                continue
        filled = filled or fill
        painting += [test, *writes, "}"]
    body += remaps + painting
    body += [f"charPut({_ASCII_ZERO}^t({low_index}));", "0;"]

    declarations = "".join(
        f"  Char {name};\n" for name in ["i", "d", "c", *"q" * filled]
    )
    if blocks > 1:
        declarations += "".join(
            f"  Integer(0,{blocks - 1},0,0) {name};\n" for name in "hg"
        )
    statements = "".join(f"  {line}\n" for line in _folded(body))
    return (
        "Package : IO {\n"
        f"{declarations}"
        f"  Array(Char,{span}) t;\n"
        "  Integer main {\n"
        f"{statements}"
        "  }\n"
        "} truthTable;\n"
    )


def _counter(first: str, second: str, weights: list[int]) -> tuple[list[str], str]:
    """Read inputs into a value, and name the register holding it.

    Each step doubles the register read so far into its partner and adds
    the new bit, so the two swap roles and the drained one is always the
    next step's target.  An input of weight 0 is read and dropped.
    """
    lines = []
    source, target = first, second
    step = 0
    for weight in weights:
        if not weight:
            lines.append("charGet(c);")
            continue
        # Nothing is read before the first input, so it has nothing to double.
        double = (
            f"While {source} Do{{DECR {source};INCR {target};INCR {target};}}"
            if step
            else ""
        )
        lines.append(f"{double}charGet(c);If c^{_ASCII_ZERO}Then{{INCR {target};}}")
        source, target = target, source
        step += 1
    return lines, source


def _writes(rows: str, *, runs: bool) -> tuple[list[str], bool]:
    """Return one block's shortest painting statements, and whether they use ``q``.

    Candidates: single writes, a fill with the zeros punched out, and (with
    ``runs``) a loop per run of ones.  ``q`` costs a declaration, so the
    caller builds both.  Run loops: -19.9%/-32.7%/-35.8% at n=7/8/9 on
    constant-leaf tables, 0% on random.
    """
    ones = rows.count("1")
    singles = [f"INCR t({row});" for row, bit in enumerate(rows) if bit == "1"]
    best, fill = singles, False
    if ones - (len(rows) - ones) > _FILL_COST:
        fill_all = f"While q^{len(rows)}Do{{INCR t(q);INCR q;}}"
        punched = [f"DECR t({row});" for row, bit in enumerate(rows) if bit == "0"]
        best, fill = [fill_all, *punched], True
    if not runs:
        return best, fill
    painted: list[str] = []
    used = False
    at = 0  # where q stands
    for match in re.finditer("1+", rows):
        start, stop = match.span()
        single = "".join(f"INCR t({row});" for row in range(start, stop))
        loop = f"While q^{stop}Do{{INCR t(q);INCR q;}}"
        if start != at:
            loop = f"While q^{start}Do{{INCR q;}}" + loop
        if len(loop) < len(single):
            painted.append(loop)
            used = True
            at = stop
        else:
            painted.append(single)
    if sum(map(len, painted)) < sum(map(len, best)):
        return painted, used
    return best, fill


def _folded(statements: list[str]) -> list[str]:
    """Pack statements into lines of at most :data:`_WIDTH` characters."""
    lines: list[str] = []
    for statement in statements:
        if not statement:
            continue
        if lines and len(lines[-1]) + len(statement) <= _WIDTH:
            lines[-1] += statement
        else:
            lines.append(statement)
    return lines
