"""lol waht i cant edit talk pages Boolean generator: a decision tree.

Each level reads the one variable ``x``, then a while-equal loop on ``1``
runs the one arm and ends in ``waht i got banned``; the zero arm follows
unguarded and runs only when that loop was skipped.  Leaves print through the
signature line ``0 --tommyaweosme``, needing no variable. An identity
node on the final input instead reads and prints ``x`` directly.

Size:
    O(T) lines; n=4 parity: 1222 chars

Decisions:
    A halt ends the one arm, where two guarded loops each ended in a bump:
    it drops the zero loop and both bumps ([ablations.halt_arm]).  One shared
    variable suffices: the zero arm tests nothing, so the one arm's reads
    cannot disturb it.
"""

from functools import cache

from esolangs.generation.helpers import _validate_truth_table, constant_span_test
from esolangs.languages.lol_waht_i_cant_edit_talk_pages.descriptor import (
    LANGUAGE as LANGUAGE,
)


def lol_waht_i_cant_edit_talk_pages(truth_table: str) -> str:
    """Build a program printing ``truth_table[row]`` for the inputs."""
    _validate_truth_table(truth_table)
    n = len(truth_table).bit_length() - 1
    constant = constant_span_test(truth_table)
    read = "im awesome tottaly but no x"

    @cache
    def build(level: int, lo: int, hi: int) -> tuple[str, ...]:
        if constant(lo, hi):
            return (*[read] * (n - level), f"{truth_table[lo]} --tommyaweosme")
        if hi - lo == 2 and truth_table[lo] == "0":
            # This is the last read: echoing earlier would skip suffix inputs.
            return (read, "i hate u x")
        mid = (lo + hi) // 2
        zero, one = build(level + 1, lo, mid), build(level + 1, mid, hi)
        if zero == one:
            return (read, *zero)
        return (
            read,
            "JUST LET ME CHANGE 1 MESSAGE ON x {",
            *one,
            "waht i got banned",
            "}",
            *zero,
        )

    return "\n".join(["user:x", *build(0, 0, 2**n)])
