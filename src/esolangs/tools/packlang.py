"""Linear Boolean-function generator for Packlang.

Packlang has no ``Else``, but two complementary ``If`` statements form a
decision-tree branch. Only one block runs: ``!(x ^ 48)`` selects zero and
``x ^ 48`` selects one. Constant subtrees fold to one result statement.

The tree has O(T) nodes for a T-entry table. Its source stays O(T) too:
whitespace is constant rather than depth-sized, and the inputs are named in
reverse depth order so the names repeated near the leaves are shortest.
Reads remain unconditional, preserving the generator input contract.
"""

from itertools import pairwise

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["packlang"]

_INDENT = "  "


def packlang(truth_table: str) -> str:
    """Build a linear-size Packlang program computing ``truth_table``."""
    n = _validate_truth_table(truth_table)

    # An interval is constant exactly when its endpoints have the same
    # transition count, avoiding recursive slicing and scans.
    changes = [0]
    for previous, current in pairwise(truth_table):
        changes.append(changes[-1] + (previous != current))

    names = [f"x{n - 1 - depth}" for depth in range(n)]

    def tree(start: int, end: int, depth: int) -> list[str]:
        if changes[start] == changes[end - 1]:
            return [f"{_INDENT * 2}INCR acc;"] if truth_table[start] == "1" else []
        half = (start + end) // 2
        name = names[depth]
        lines = [f"{_INDENT * 2}If !({name} ^ {_ASCII_ZERO}) Then {{"]
        lines.extend(tree(start, half, depth + 1))
        lines.append(f"{_INDENT * 2}}}")
        lines.append(f"{_INDENT * 2}If {name} ^ {_ASCII_ZERO} Then {{")
        lines.extend(tree(half, end, depth + 1))
        lines.append(f"{_INDENT * 2}}}")
        return lines

    declarations = "".join(f"  Char {name};\n" for name in names)
    reads = "".join(f"{_INDENT * 2}charGet({name});\n" for name in names)
    body = "\n".join(tree(0, 1 << n, 0))
    if body:
        body += "\n"
    return (
        "Package : IO {\n"
        f"{declarations}"
        "  Integer(0, 1, 1, 0) acc;\n"
        "  Integer main {\n"
        f"{_INDENT * 2}INIT acc;\n"
        f"{reads}"
        f"{body}"
        f"{_INDENT * 2}charPut({_ASCII_ZERO} ^ acc);\n"
        f"{_INDENT * 2}0;\n"
        "  }\n"
        "} truthTable;\n"
    )
