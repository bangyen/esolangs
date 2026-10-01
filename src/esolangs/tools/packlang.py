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
and its zeros punched back out, so a constant table pays per *block*.

Every row runs every write. The answer prints ``48 ^ t`` over painted
ones; retiring the opposite polarity adds 3.19% to the three-input total
and 2.60% to the seeded five-input sample.

The index is counted too: each input doubles what has been read and adds
its bit.  Doubling drains one register into its partner two counts at a
time, so the two alternate and no copy is ever needed.
"""

import re
from itertools import pairwise

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table
from esolangs.tools.wrap import (
    _PACKLANG_LEXEME,
    _join_tokens,
    _packlang,
    balance_score,
)

__all__ = ["packlang"]

#: Inputs the array block spans.  It bounds the index digits every painted
#: row pays, and the rows a fill loop has to walk.
_BLOCK = 7

#: Fills cheaper than this many writes are not worth the loop that fills.
_FILL_COST = 3

#: Where a run of statements folds.  Whitespace is not a Packlang token, so
#: a break costs one character per line rather than one per statement.
_WIDTH = 72


def packlang(truth_table: str, width: int | None = None) -> str:
    """Build a linear-size Packlang program; narrow layouts floor at one token.

    The unused package name shortens below ten columns; keywords floor at seven.
    """
    n = _validate_truth_table(truth_table)
    program = _painted(truth_table, n)
    if width is None or width <= 0:
        return program
    # The package is never named by its own body or the IO dependency.
    if width < len("truthTable"):
        program = program.removesuffix("} truthTable;\n") + "} t;\n"
    from esolangs.tools.wrap import wrap_program

    return wrap_program(program, "packlang", width)


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
        moving_width: int | None = None
        for line, tokens, indent, longest in records:
            if len(line) <= start:
                height += 1
                continue
            padding = min(indent, max(0, start - longest))
            rows = _join_tokens(tokens, max(1, start - padding), " ").split("\n")
            height += len(rows)
            span = max(map(len, rows))
            if longest <= start < longest + indent:
                offset = span - longest
                moving_width = (
                    max(moving_width, offset) if moving_width is not None else offset
                )
        candidates.append(start)
        # Height is fixed between fits. Only reduced indentation grows with
        # width, so its crossing of height is the other possible minimum.
        if moving_width is not None:
            candidates.append(min(max(height - moving_width, start), stop - 1))
    return min((_packlang(program, width) for width in candidates), key=balance_score)


def balance_packlang(_table: str, default: str) -> str:
    """Compare token-fit layouts with the two package-name spellings."""
    short = default.removesuffix("} truthTable;\n") + "} t;\n"
    maximum = max(map(len, default.split("\n"))) - 1
    return min(
        default,
        _balance_form(default, 10, maximum),
        _balance_form(short, 1, 9),
        key=balance_score,
    )


def _painted(painted: str, n: int) -> str:
    """Return a program painting ``painted``'s ones into an array."""
    low = min(n, _BLOCK)
    span = 1 << low
    blocks = 1 << (n - low)

    body: list[str] = []
    index = "i"
    if blocks > 1:
        picked, index = _counter("h", "g", n - low)
        body += picked
    counted, low_index = _counter("i", "d", low)
    body += counted

    filled = False
    for number in range(blocks):
        rows = painted[number * span : (number + 1) * span]
        writes, fill = _writes(rows)
        filled = filled or fill
        if not writes:
            continue
        guard = f"If !({index}^{number})Then{{" if blocks > 1 else ""
        body += [guard, *writes, "}" if guard else ""]
    body += [f"charPut({_ASCII_ZERO}^t({low_index}));", "0;"]

    names = ["i", "d", "c"] + (["q"] if filled else [])
    if blocks > 1:
        names += ["h", "g"]
    wide = f"Integer(0,{blocks - 1},0,0)"
    declarations = "".join(
        f"  {wide if name in {'h', 'g'} else 'Char'} {name};\n" for name in names
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


def _counter(first: str, second: str, count: int) -> tuple[list[str], str]:
    """Read ``count`` inputs into a value, and name the register holding it.

    Each step doubles the register read so far into its partner and adds
    the new bit, so the two swap roles and the drained one is always the
    next step's target.
    """
    lines = []
    source, target = first, second
    for step in range(count):
        # Nothing is read before the first input, so it has nothing to double.
        double = (
            f"While {source} Do{{DECR {source};INCR {target};INCR {target};}}"
            if step
            else ""
        )
        lines.append(f"{double}charGet(c);If c^{_ASCII_ZERO}Then{{INCR {target};}}")
        source, target = target, source
    return lines, source


def _writes(rows: str) -> tuple[list[str], bool]:
    """Return one block's painting statements, and whether they fill it first."""
    ones = rows.count("1")
    if ones - (len(rows) - ones) <= _FILL_COST:
        return [f"INCR t({row});" for row, bit in enumerate(rows) if bit == "1"], False
    fill = f"While q^{len(rows)}Do{{INCR t(q);INCR q;}}"
    punched = [f"DECR t({row});" for row, bit in enumerate(rows) if bit == "0"]
    return [fill, *punched], True


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
