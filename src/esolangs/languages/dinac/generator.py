"""DINAC Boolean program generator: a flat scan over the rows.

Each input is read once into a variable named by its height (``b0`` the last
input).  A flag ``f<h>`` holds whether the inputs of height >= h equal the
current row's bits; it is rewritten (``and`` of its parent and one
comparison) only when that prefix changes, which is ``tz(row)`` flags per
row, T-1 in all.  Each 1-row folds ``and(f1, b0 = bit)`` into ``a`` with
``or``; the interpreter evaluates the whole scan and the program prints ``a``.
No branch nests, so a line costs a constant number of characters.

Size:
    Linear in T: at most 51T + 18n + 120 characters; names are indexed by
    height, so the T/2**h references to height h cost O(1) on average
    (sum of T * len(h) / 2**h); n=4 parity: 767 chars

Decisions:
    A nested IF/ELSE tree costs 4 spaces of indent per level on every leaf,
    T log T characters; a function per subtree needs a name per subtree,
    again log T each.  The scan has neither.
"""

from esolangs.generation.helpers import _validate_truth_table
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
    lines = list(_PRELUDE)
    for h in range(n - 1, -1, -1):
        lines += [f"SET b{h}:\\0", f"IN b{h}"]
    lines.append("SET a:00")
    for row, entry in enumerate(truth_table):
        for h in _refreshed(row, n):
            test = f"b{h} = '{row >> h & 1}"
            expr = test if h == n - 1 else f"and(f{h + 1}, {test})"
            lines.append(f"SET f{h}:{expr}" if row == 0 else f"f{h} . {expr}")
        if entry == "1":
            test = f"b0 = '{row & 1}"
            lines.append(f"a . or(a, {test if n == 1 else f'and(f1, {test})'})")
    lines += ["IF a", "    OUT '1", "ELSE", "    OUT '0"]
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
