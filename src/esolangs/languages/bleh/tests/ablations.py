"""Independent diagram spelling with the short read alias disabled."""

from itertools import pairwise
from string import ascii_letters
from typing import Literal

from esolangs.generation.helpers import _validate_truth_table, subtree_ids


def _name(node: int, level: int) -> str:
    if node < 2:
        return f"{'zo'[node]}{level}"
    letters = []
    while node:
        node, digit = divmod(node - 1, 52)
        letters.append(ascii_letters[digit])
    return "".join(reversed(letters))


def ablate(table: str, rule: Literal["default", "read_alias"]) -> str:
    """Disable the alias, retaining the old constant blocks it made necessary."""
    n = _validate_truth_table(table)
    short = rule == "default"
    read = "2()" if short else "a::next()"
    header = "^:std::io=a;" + ('2:=3 a::next();3:"0"="0":"1"="1";' if short else "")
    if len(set(table)) == 1:
        if short:
            return header + "main:={" + (read + ";") * n + f'a::print"{table[0]}"}};'
        chunks = [2] * ((n - 1) // 2) + ([1] if (n - 1) % 2 else []) + [1]
        names = ["main", *(_name(int(table[0]), k + 1) for k in range(len(chunks) - 1))]
        bodies = []
        for k, (name, count) in enumerate(zip(names, chunks, strict=True)):
            tail = (
                names[k + 1] + "()" if k + 1 < len(names) else f'a::print"{table[0]}"'
            )
            bodies.append(name + ":={" + (read + ";") * count + tail + "};")
        return header + "".join(bodies)
    ids = subtree_ids(table)
    levels = [
        {key: (below[2 * k], below[2 * k + 1]) for k, key in enumerate(above)}
        for above, below in pairwise(ids)
    ]

    def ref(key: int, level: int) -> str:
        if level == n:
            return f'a::print"{key}"'
        lo, hi = levels[level][key]
        return _name(key, level) + ("()" if lo == hi else " " + read)

    bodies = []
    for level, nodes in enumerate(levels):
        for key, (lo, hi) in nodes.items():
            name = _name(key, level)
            zero = ref(lo, level + 1)
            body = (
                ":={" + read + ";" + zero + "}"
                if lo == hi
                else f':"0"={zero}:"1"={ref(hi, level + 1)}'
            )
            bodies.append(name + body + ";")
    return header + "main:=" + ref(ids[0][0], 0) + ";" + "".join(bodies)
