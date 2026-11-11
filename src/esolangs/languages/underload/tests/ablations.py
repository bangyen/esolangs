"""Independent Underload carry tree and terminal-drop ablation."""

from functools import cache
from typing import Literal

from esolangs._bindings import TEMPLATE_CHAR
from esolangs.generation.helpers import (
    SubtreeDiagram,
    _validate_truth_table,
    reflected_table,
)
from esolangs.languages.underload.generator import _REACH, PAIR


def _family(table: str, n: int) -> bool:
    ones = table.count("1")
    count = min(ones, len(table) - ones)
    if count not in (1, n + 1):
        return False
    bit = "1" if ones <= len(table) // 2 else "0"
    positions = {i for i, value in enumerate(table) if value == bit}
    top = len(table) - 1
    near_zero = {0, *(1 << i for i in range(n))}
    return positions in ({0}, {top}, near_zero, {top ^ i for i in near_zero})


def ablate(truth_table: str, rule: Literal["default", "terminal_drops"]) -> str:
    """Build independently with the named family's terminal cleanup disabled."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return f"({truth_table[0]})" + TEMPLATE_CHAR * (3 * n) + "!" * n + "S"
    drop = "\ue000" if rule == "default" and _family(truth_table, n) else "!"
    diagram = SubtreeDiagram(reflected_table(truth_table, n))
    halves, level_of, reaches = diagram.halves, diagram.level, diagram.reaches

    # Preserve the old carry prices while erasing only named terminal drops.
    @cache
    def tree(level: int, key: int, carry: int | None) -> str:
        if carry is not None and key == carry:
            return "^"
        if carry is not None and not reaches(key, carry):
            return (drop if key < 2 else "!") + tree(level, key, None)
        if key < 2:
            return drop * (n - level) + f"({key})"
        if carry is None:
            return min((node(level, key, None), *carried(level, key)), key=len)
        return node(level, key, carry)

    def node(level: int, key: int, carry: int | None) -> str:
        zero, one = halves[key]
        opening = "" if carry is None else "~"
        if zero == one:
            return opening + (drop if zero < 2 else "!") + tree(level + 1, zero, carry)
        closing = ")~^"
        zero_text, one_text = tree(level + 1, zero, carry), tree(level + 1, one, carry)
        return opening + "(" + zero_text + ")~(" + one_text + closing

    @cache
    def carried(level: int, key: int) -> list[str]:
        """Return the shortest ``(X)`` push and carry over the ``X`` worth it."""
        candidates = (
            "(" + tree(level_of[name], name, None) + ")" + tree(level, key, name)
            for name in diagram.repeated_near(key, _REACH)
        )
        # Race kept: it saves 47-60% on majority (n=8,10), 41-49% on
        # threshold-3, 11% on random tables.
        return sorted(candidates, key=len)[:1]  # stable: the first shortest

    body = tree(0, diagram.root, None).replace("\ue000", "")
    slots = TEMPLATE_CHAR * (len(PAIR[0]) * n)
    return slots + "(" + body + ")^S"
