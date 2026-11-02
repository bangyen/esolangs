"""Independent Rubic trees with the last-input literal spelling disabled."""

from typing import Literal

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.languages.rubic.generator import _OPENING, _TABLE


def ablate(table: str, rule: Literal["default", "last_bit_literal"]) -> str:
    """Return the native tree with only the named literal rule disabled."""
    n = _validate_truth_table(table)
    if len(set(table)) == 1:
        return " ".join(
            (
                *_OPENING,
                *_TABLE["read"][:3],
                *["!"] * n,
                ")",
                *_TABLE["print" + table[0]],
            )
        )
    ranks = subtree_ids(table)
    tokens = list(_OPENING)

    def emit(depth: int, index: int) -> None:
        value = ranks[depth][index]
        if value < 2:
            tokens.extend(_TABLE["read"] * (n - depth))
            tokens.extend(_TABLE[f"print{value}"])
            return
        tokens.extend(_TABLE["read"])
        if rule != "last_bit_literal" and depth + 1 == n:
            if table[2 * index] == "0":
                tokens.append("!")
            else:
                tokens.extend(
                    (
                        *_TABLE["bit"],
                        "(",
                        "r2",
                        ")",
                        *_TABLE["not"],
                        "!",
                        *_TABLE["P"],
                        "(",
                        "r2",
                        ")",
                    )
                )
            return
        if ranks[depth + 1][2 * index] == ranks[depth + 1][2 * index + 1]:
            emit(depth + 1, 2 * index)
            return
        tokens.extend((*_TABLE["bit"], "(", "r2", ")", *_TABLE["Q"], "("))
        emit(depth + 1, 2 * index)
        tokens.extend((")", *_TABLE["P"], "(", "r2"))
        emit(depth + 1, 2 * index + 1)
        tokens.append(")")

    emit(0, 0)
    return " ".join(tokens)
