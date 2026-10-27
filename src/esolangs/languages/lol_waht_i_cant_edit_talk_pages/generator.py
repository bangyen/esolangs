"""lol waht i cant edit talk pages Boolean generator: a decision tree.

Each level reads its input into its own variable, then runs two
while-equal loops as if-branches: ``ON 1`` takes the one arm, ``ON no``
the zero arm.  Each arm ends by adding 1, which leaves its loop and
misses the other (1 becomes 2, 0 becomes 1).  Leaves print through the
signature line ``0 --tommyaweosme``, needing no variable.

Size:
    O(T) lines; n=4 parity: 3123 chars

Decisions:
    One variable per level, not one shared flag: an arm's reads would
    overwrite a shared flag before the zero loop tests it.
"""

from functools import cache

from esolangs.generation.helpers import _validate_truth_table, constant_span_test
from esolangs.registry._language import Language


def lol_waht_i_cant_edit_talk_pages(truth_table: str) -> str:
    """Build a program printing ``truth_table[row]`` for the inputs."""
    _validate_truth_table(truth_table)
    n = len(truth_table).bit_length() - 1
    constant = constant_span_test(truth_table)

    @cache
    def build(level: int, lo: int, hi: int) -> tuple[str, ...]:
        if constant(lo, hi):
            reads = [f"im awesome tottaly but no x{d}" for d in range(level, n)]
            return (*reads, f"{truth_table[lo]} --tommyaweosme")
        mid = (lo + hi) // 2
        read = f"im awesome tottaly but no x{level}"
        zero, one = build(level + 1, lo, mid), build(level + 1, mid, hi)
        if zero == one:
            return (read, *zero)
        bump = f"edit user talk:x{level} to change 1 messages"
        return (
            read,
            f"JUST LET ME CHANGE 1 MESSAGES ON x{level} {{",
            *one,
            bump,
            "}",
            f"JUST LET ME CHANGE no MESSAGES ON x{level} {{",
            *zero,
            bump,
            "}",
        )

    lines = [f"user:x{d}" for d in range(n)] + list(build(0, 0, 2**n))
    return "\n".join(lines)


LANGUAGE = Language(
    "lol waht i cant edit talk pages",
    "lol_waht_i_cant_edit_talk_pages",
    category="variable_based",
    boolean=lol_waht_i_cant_edit_talk_pages,
    no_wrap="every statement is one line, so a break splits a command",
)
