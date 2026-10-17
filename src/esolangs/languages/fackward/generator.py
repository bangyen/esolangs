"""Fackward Boolean program generator: a decision tree of nested blocks.

Each pass reads the sequence reversed; a quiet one reads a character onto
the far end.  A level deblocks to ``[B] )``, quiet, so the bit arrives and
the next pass deblocks ``B``: ``~ / c`` turns ``/ c 49`` into the bit,
``~ $ b`` makes ``b`` copies of a ``~`` that swaps the child blocks, ``!``
drops one and ``)`` runs the other.  Leaves print and halt; equal halves
drop the character with ``! c``.  Each function is released one pass
before it runs, so nothing fires early.

Size:
    37T - 31 chars without equal halves, O(n) for a constant; repeated
    subtables are copied; 40n + 4 steps at most; n=10 parity: 37,857
    chars, n=10 random 1847: 26,349 chars.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.wrap import TokenWrapper
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language


def _node(zero: str, one: str) -> str:
    """A level choosing ``zero``'s or ``one``'s contents by the bit read."""
    return f")[/~[[$~[)[[!))[]])][{one}][{zero}]~])])49])]"


def _skip(child: str) -> str:
    """A level that reads its bit, drops it, and goes on to ``child``."""
    return f")[![{child}])]"


def _contents(table: str, memo: dict[str, str]) -> str:
    """The block contents of ``table``'s level, leaves printing and halting."""
    if table not in memo:
        if len(table) == 1:
            memo[table] = f"H{48 + int(table)}"
        else:
            half = len(table) // 2
            zero = _contents(table[:half], memo)
            one = _contents(table[half:], memo)
            memo[table] = _skip(zero) if zero == one else _node(zero, one)
    return memo[table]


def fackward(truth_table: str) -> str:
    """Build a Fackward program printing ``truth_table[row]`` for the inputs."""
    _validate_truth_table(truth_table)
    return f")[{_contents(truth_table, {})}]"


#: Break anywhere but inside a number, which a newline would split.
_wrap = TokenWrapper(r"\d+|[\s\S]")


LANGUAGE = Language(
    "Fackward",
    "fackward",
    category="stack_based",
    boolean=fackward,
    contract=BooleanContract(input_shape="char_stream"),
    eof="a read at EOF halts the run",
    # Whitespace only separates tokens, so a newline between two is harmless.
    wrap=_wrap,
)
