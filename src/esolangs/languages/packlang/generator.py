"""Packlang Boolean program generator: a painted 128-row array, read by index.

``Array`` starts every element at the type's minimum, so a table is painted
rather than branched.  Inputs above the block index are read into a block
number; each block paints the array inside the ``If`` that selects it; the
answer prints ``48 ^ t`` at the counted index.  A row costs one ``INCR t(k);``
(writes count, so nothing is shorter) with ``k`` an offset inside the block,
so digits stop growing past one block. Filling and punching out zeros is
a candidate when the surplus of ones pays the fixed loop cost; an all-zero block paints
nothing; a block equal to an earlier one is aliased to it (:func:`_blocks`
shrinks the block until repeats align).  Each input doubles the register read
so far into its partner two counts at a time and adds its bit, so the two
alternate and no copy is needed.

``balance=True`` also repacks the body past :data:`_WIDTH` (:func:`_refolded`);
the default's 72-column lines capped a fit at narrowing, so balanced area
grew as T^2 (74x105 at n=10).

Size:
    O(T) characters; whole constants use one byte and n reads;
    n=8 zero: 166 chars; n=8 and: 659 chars, n=10 and: 796 chars,
    n=10 random 1847: 6,677 chars.

Decisions:
    The complement painted and printed as ``49 ^ t`` races the direct paint;
    see ``[ablations.complement_paint]``.  The execution bound is the direct
    paint's worst, no longer reached.
"""

import re
from collections.abc import Sequence
from itertools import product

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    grid_width,
    input_weights,
    subtree_ids,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.token_balance import balanced_token_width, run_widths
from esolangs.generation.wrap import (
    _join_tokens,
    balance_score,
    wrap_program,
)
from esolangs.languages.packlang.dialect import (
    PacklangLiterals,
)
from esolangs.languages.packlang.wrapping import (
    _PACKLANG_LEXEME,
    _packlang,
)
from esolangs.runtime._program import Program

__all__ = ["packlang"]

#: Inputs the array block spans.  It bounds the index digits every painted
#: row pays, and the rows a fill loop has to walk.  Essential as a cap: one
#: 512-row array (n=9) did not terminate in 30 s (Char index wraps).  The
#: value is flat on random tables ([ablations.block_cap]).
_BLOCK = 7

#: The smallest block :func:`_blocks` tries; below it index digits dominate.
_MIN_BLOCK = 4

#: Fills cheaper than this many writes are not worth the loop that fills.
#: Dropping fill+punch costs most on dense tables ([ablations.fill_punch]).
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
    if not any(weights):
        candidates = [_constant_program(len(weights), int(table))]
    else:
        complement = table.translate(str.maketrans("01", "10"))
        candidates = [
            _painted(
                complement if flip else table,
                weights,
                runs=runs,
                block=block,
                flip=flip,
            )
            for (runs, block), flip in product(
                product((False, True), _blocks(table)), (False, True)
            )
        ]
    built = []
    for candidate in candidates:
        program = candidate
        if literal_policy != "decimal":
            program = re.sub(
                r"(?<!\w)\d+", lambda match: literals.emit(int(match[0])), program
            )
        if width is not None and width > 0:
            # The package is never named by its own body or the IO dependency.
            if width < _NAME_LEN:
                program = _short_name(program)
            program = wrap_program(program, "packlang", width)
        built.append(program)
    return min(built, key=len)


def _constant_program(n: int, bit: int) -> str:
    """Read into one byte, then print the constant without an array."""
    # [ablations.constant_table_audit_20261101].
    # main has no caller; its implicit zero result needs no trailing expression.
    # [ablations.trailing_value_drop].
    body = ["charGet(c);"] * n + [f"charPut({_ASCII_ZERO + bit});"]
    statements = "".join(f"  {line}\n" for line in _folded(body))
    return (
        "Package : IO {\n  Char c;\n  Integer main {\n"
        + statements
        + "  }\n} truthTable;\n"
    )


def _blocks(table: str) -> list[int]:
    """Return the block sizes (log2 rows) to build.

    :data:`_BLOCK`, plus each smaller one where two blocks are equal and can
    alias; a single block cannot, so repeats shorter than it were never
    shared. Earlier tiled-table figures were not reproduced
    ([ablations.smaller_block_offers]); random tables offer none.
    """
    n = len(table).bit_length() - 1
    top = min(n, _BLOCK)
    if n <= _MIN_BLOCK:  # also a constant table, whose projection has n = 0
        return [top]
    ids = subtree_ids(table)
    smaller = [
        low for low in range(_MIN_BLOCK, top) if len(set(ids[n - low])) < 1 << (n - low)
    ]
    return [top, *smaller]


def _short_name(program: str) -> str:
    return program.removesuffix("} truthTable;\n") + "} t;\n"


def _balance_form(program: str, minimum: int, maximum: int) -> str:
    """Balance at statement fits and reduced-indentation transitions.

    Height is fixed between them and only reduced indentation grows with
    width, so each interval's first width renders its smallest square.
    """
    events = {minimum}
    for line in program.split("\n"):
        tokens = re.findall(_PACKLANG_LEXEME, line)
        indent = len(line) - len(line.lstrip())
        longest = max(map(len, tokens), default=0)
        events.update((len(line), longest, indent + longest))
        for span in run_widths(list(map(len, tokens))):
            events.update((span, indent + span))
    starts = sorted(point for point in events if minimum <= point <= maximum)
    return min((_packlang(program, width) for width in starts), key=balance_score)


def _refolded(program: str) -> str:
    """Return ``program`` with the body refolded to its balanced width.

    The default folds at :data:`_WIDTH`, and a fit can only narrow a line, so
    the rows grew with T and balanced side with 2 * T / 72.  The body is
    cut after each ``;``, ``{`` and ``}`` and packed at the width that
    renders squarest.
    """
    head, mid, tail = program.partition("  Integer main {\n")
    body, end, rest = tail.partition("  }\n}")
    atoms = re.findall(
        r"[^;{}]*[;{}]", "".join(line.strip() for line in body.split("\n"))
    )
    if (
        not mid
        or not end
        or "".join(atoms) != "".join(map(str.strip, body.split("\n")))
    ):
        return program
    width = balanced_token_width(atoms, minimum=_NAME_LEN)
    candidates = []
    for wide in range(max(_NAME_LEN, width - 3), width + 4):
        lines = _join_tokens(atoms, wide, separator="").split("\n")
        folded = "".join(f"  {line}\n" for line in lines)
        candidates.append(head + mid + folded + end + rest)
    return min(candidates, key=balance_score)


def balance_packlang(_table: str, default: str) -> str:
    """Compare ``default`` with token-fit layouts and the refolded body."""
    maximum = grid_width(default) - 1
    return min(
        default,
        _balance_form(default, _NAME_LEN, maximum),
        _refolded(default),
        key=balance_score,
    )


def _painted(
    painted: str, weights: Sequence[int], *, runs: bool, block: int, flip: bool = False
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

    remaps, painting, filled = _paint_blocks(
        painted, index, span, blocks, n - low, runs=runs
    )
    body += remaps + painting
    # No expression statements: main already has its implicit zero result.
    body += [f"charPut({_ASCII_ZERO + flip}^t({low_index}));"]

    names = ["i", "d", "c"] + (["q"] if filled else [])
    declarations = "".join(f"  Char {name};\n" for name in names)
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


def _paint_blocks(
    painted: str, index: str, span: int, blocks: int, depth: int, *, runs: bool
) -> tuple[list[str], list[str], bool]:
    """Return the alias lines, the block writes, and whether any uses ``q``."""
    filled = False
    # A block equal to an earlier one is remapped onto it: the index is
    # decremented to the first copy's number before any block tests it
    # ([ablations.block_aliasing]).
    ids = subtree_ids(painted)[depth] if blocks > 1 else []
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
    return remaps, painting, filled


def _counter(first: str, second: str, weights: Sequence[int]) -> tuple[list[str], str]:
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
    caller builds both. Run loops pay most on constant-leaf tables and
    sometimes on random ones ([ablations.run_loops]).
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


def packlang_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    if request.width is not None:
        return packlang(
            request.table,
            request.width,
            literal_policy=request.options.text("literal_policy"),
        )
    return packlang(
        request.table, literal_policy=request.options.text("literal_policy")
    )


def packlang_balance_request(request: BalanceRequest) -> Program:
    """Lay out source through the declared balance request interface."""
    return balance_packlang(request.table, request.text_source())
