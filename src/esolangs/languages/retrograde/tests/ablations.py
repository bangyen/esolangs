"""Independent inline-tree emitters with one canonical/minimal rule disabled."""

from typing import Literal

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.languages.retrograde.generator import _moves

Rule = Literal["default", "constant_fold", "ignored_input", "inverse_moves"]


def ablate(table: str, rule: Rule) -> str:
    """Return the same native tree with exactly the named rule disabled."""
    n = _validate_truth_table(table)
    ids = subtree_ids(table)
    constants = rule != "constant_fold"
    prefix = "$>" * n
    if constants and ids[0][0] < 2:
        return prefix + ("*" if ids[0][0] else "")
    chunks = [prefix, "<" * n]

    def body(depth: int, k: int) -> None:
        if constants and ids[depth][k] == 0:
            return
        chunks.append(">")
        tree(depth, k)
        chunks.append("<")

    def tree(depth: int, k: int) -> None:
        node = ids[depth][k]
        if depth == n or (constants and node < 2):
            if node:
                chunks.extend((">" * (n - depth), "*", "<" * (n - depth)))
            return
        zero, one = 2 * k, 2 * k + 1
        # Constant children cannot be collapsed by the ignored-input mutant.
        if (
            rule != "ignored_input"
            and node >= 2
            and ids[depth + 1][zero] == ids[depth + 1][one]
        ):
            body(depth + 1, zero)
            return
        chunks.append("*{{*")
        body(depth + 1, one)
        chunks.append("}{*")
        body(depth + 1, zero)
        chunks.append("}}")

    tree(0, 0)
    chunks.append(">" * n)
    source = "".join(chunks)
    return source if rule == "inverse_moves" else _moves(source)
