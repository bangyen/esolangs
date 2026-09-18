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
    lines: list[str] = []  # one flat list, appended at the leaves: O(2**n)

    def tree(start: int, end: int, depth: int) -> None:
        if changes[start] == changes[end - 1]:
            if truth_table[start] == "1":
                lines.append(f"{_INDENT * 2}INCR acc;")
            return
        half = (start + end) // 2
        name = names[depth]
        lines.append(f"{_INDENT * 2}If !({name} ^ {_ASCII_ZERO}) Then {{")
        tree(start, half, depth + 1)
        lines.append(f"{_INDENT * 2}}}")
        lines.append(f"{_INDENT * 2}If {name} ^ {_ASCII_ZERO} Then {{")
        tree(half, end, depth + 1)
        lines.append(f"{_INDENT * 2}}}")

    declarations = "".join(f"  Char {name};\n" for name in names)
    reads = "".join(f"{_INDENT * 2}charGet({name});\n" for name in names)
    tree(0, 1 << n, 0)
    body = "\n".join(lines)
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
