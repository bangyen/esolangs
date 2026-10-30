"""DINAC Boolean program generator: a flat scan over the rows.

Each input is read once into a variable named by its height (``b0`` the last
input).  A flag ``f<h>`` holds whether the inputs of height >= h equal the
current row's bits; it is rewritten (``and`` of its parent and one
comparison) only when that prefix changes, which is ``tz(row)`` flags per
row, T-1 in all.  Each 1-row folds ``and(f1, b0 = bit)`` into ``a`` with
``or``; the interpreter evaluates the whole scan and the program prints ``a``.
Only essential inputs get a height; an ignored input is read into a scratch
variable and a constant table is read and printed with no scan.
No branch nests, so a line costs a constant number of characters.

Size:
    Linear in T: at most 40T + 18n + 120 characters; names are indexed by
    height, so the T/2**h references to height h cost O(1) on average
    (sum of T * len(h) / 2**h); n=4 parity: 767 chars

Decisions:
    A nested IF/ELSE tree costs 4 spaces of indent per level on every leaf,
    T log T characters; a function per subtree needs a name per subtree,
    again log T each.  The scan has neither.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

__all__ = ["dinac"]

_PRELUDE = (
    "DEF/00 and a:00 b:00",
    "    IF a",
    "        GIVE ~~b",
    "    ELSE",
    "        GIVE 00",
    "DEF/00 or a:00 b:00",
    "    IF a",
    "        GIVE 01",
    "    ELSE",
    "        GIVE ~~b",
)


def _refreshed(row: int, n: int) -> range:
    """The flag heights that change entering ``row``, parents first."""
    # Entering a row flips the bits of height <= its trailing zeros; row 0
    # sets every flag.
    top = n - 1 if row == 0 else (row & -row).bit_length() - 1
    return range(top, 0, -1)


def dinac(truth_table: str) -> str:
    """Build a DINAC program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    # Scan the rarer answer's rows and invert the print; the OR lines are the
    # only part that depends on the table, so the rarer side is the shorter
    # build (ties scan the 1-rows).
    # Ignored inputs are read into one scratch variable and left out of the
    # scan; a constant table prints its answer with no scan at all.
    keep = essential_inputs(truth_table, n)
    if not keep:
        return "\n".join([*_reads(n, keep), f"OUT '{truth_table[0]}"])
    table = read_at(truth_table, keep, n)
    mark = "1" if 2 * table.count("1") <= len(table) else "0"
    return _scan(table, len(keep), mark, _reads(n, keep))


def _reads(n: int, keep: list[int]) -> list[str]:
    """Read every input in order: kept ones into ``b<height>``, the rest into ``x``."""
    lines = ["SET x:\\0"] if len(keep) < n else []
    for i in range(n):
        if i in keep:
            h = len(keep) - 1 - keep.index(i)
            lines += [f"SET b{h}:\\0", f"IN b{h}"]
        else:
            lines.append("IN x")
    return lines


def _scan(truth_table: str, n: int, mark: str, reads: list[str]) -> str:
    """The scan that ORs the ``mark`` rows and prints ``a`` or its complement."""
    lines = [*_PRELUDE, *reads]
    lines.append("SET a:00")
    for row, entry in enumerate(truth_table):
        for h in _refreshed(row, n):
            test = f"b{h} = '{row >> h & 1}"
            expr = test if h == n - 1 else f"and(f{h + 1}, {test})"
            lines.append(f"SET f{h}:{expr}" if row == 0 else f"f{h} . {expr}")
        if entry == mark:
            test = f"b0 = '{row & 1}"
            lines.append(f"a . or(a, {test if n == 1 else f'and(f1, {test})'})")
    lines += ["IF a", f"    OUT '{mark}", "ELSE", f"    OUT '{1 - int(mark)}"]
    return "\n".join(lines)


LANGUAGE = Language(
    "DINAC",
    "dinac",
    category="other",
    boolean=dinac,
    shape=Shape.LOOKUP,
    contract=BooleanContract(input_shape="char_stream"),
    eof="reading past the input yields \\0 / 00, the value the cat example needs",
    no_wrap="each line is one statement and indentation is the block structure",
)
