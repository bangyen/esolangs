"""Independent named diagrams and bounded literal-head cost choices."""

from collections import Counter
from typing import Literal

from esolangs.generation.helpers import _validate_truth_table, subtree_ids


def ablate(table: str, rule: Literal["default", "inline_literals"]) -> str:
    """Return the hybrid, or disable its literal-head construction."""
    n = _validate_truth_table(table)
    if len(set(table)) == 1:
        head = "$" if n == 1 else "(" + " ".join("$" * n) + ")"
        return f"x->s[]={table[0]};{head}->s[]"
    ranks = subtree_ids(table)
    edges: dict[int, tuple[int, int]] = {}
    for depth, level in enumerate(ranks[:-1]):
        for offset, value in enumerate(level):
            if value > 1:
                edges[value] = (
                    ranks[depth + 1][2 * offset],
                    ranks[depth + 1][2 * offset + 1],
                )
    counts = Counter({ranks[0][0]: 1})
    for zero, one in edges.values():
        counts[zero] += 1
        if zero != one:
            counts[one] += 1
    words = {0: "0", 1: "1"}
    atoms = {0: 1, 1: 1}
    definitions: dict[int, str] = {}
    declared = set()
    for value in sorted(edges):
        # ids ascend from children to parents, independent of traversal order.
        zero, one = edges[value]
        name, low, high = str(value), words[zero], words[one]
        eq = (
            f"{name}->s[x]={low};"
            if zero == one
            else f"{name}->s[0]={low};{name}->s[1]={high};"
        )
        literal = f"({low} {high})"
        payload = atoms[zero] + atoms[one]
        if (
            rule != "inline_literals"
            and payload <= 2 * n
            and counts[value] * (len(literal) - len(name)) < len(eq)
        ):
            words[value], atoms[value] = literal, payload
        else:
            words[value], atoms[value] = name, len(name)
            declared.add(value)
        definitions[value] = eq
    prefix = "(l h)->s[0]=l;(l h)->s[1]=h;" if len(declared) < len(edges) else ""
    return (
        prefix
        + "".join(definitions[value] for value in edges if value in declared)
        + "c->s[x]=c;"
        + words[ranks[0][0]]
        + "->s[$]" * n
    )
