"""Independent Codesick diagram with decimal/hash names as the ablation."""

from collections import Counter
from itertools import pairwise
from string import ascii_letters, digits, punctuation
from typing import Literal

from esolangs.generation.helpers import reflected_table, subtree_ids


def ablate(table: str, rule: Literal["default", "dense_names"]) -> str:
    """Return the same graph with short non-bit names or decimal hash markers."""
    ids = subtree_ids(reflected_table(table, len(table).bit_length() - 1))
    kids: dict[int, tuple[int, int]] = {}
    for above, below in pairwise(ids):
        for i, key in enumerate(above):
            if key >= 2:
                kids.setdefault(key, (below[2 * i], below[2 * i + 1]))
    if not kids:
        return f"codesick out {ids[0][0]} in * *;"
    counts = Counter(c for pair in kids.values() for c in pair)
    names = {k: str(k) for k in kids}
    if rule == "default":
        alphabet = "".join(
            c for c in ascii_letters + digits + punctuation if c not in '01#*;"'
        )
        rank = 1
        for k in sorted(kids, key=lambda k: -counts[k]):
            while True:
                value, name = rank, ""
                while value:
                    value, digit = divmod(value - 1, len(alphabet))
                    name = alphabet[digit] + name
                rank += 1
                if name not in {"in", "out", "codesick"}:
                    break
            names[k] = name
    marker = {k: ("#" if rule == "dense_names" else "") + v for k, v in names.items()}
    entry = {0: "0", 1: "1"} | names
    hit = {}
    for k, pair in kids.items():
        hit[k] = min(
            (0, 1),
            key=lambda b: (
                (pair[b] < 2 or counts[pair[b]] > 1) + (pair[1 - b] >= 2),
                b,
            ),
        )
        if pair[hit[k]] >= 2 and counts[pair[hit[k]]] == 1:
            entry[pair[hit[k]]] = f"{hit[k]}{marker[k]}"
    lines, printed = [], set()
    for k, pair in kids.items():
        b = hit[k]
        h, m = pair[b], pair[1 - b]
        yes, no = f"{b}{marker[k]}", f"{1 - b}{marker[k]}"
        miss = str(m) if m < 2 else no
        lines.append(f"{entry[k]} codesick in {marker[k]} {yes} {miss};")
        if entry[h] != yes:
            lines.append(
                f"{yes} codesick out {h} * *;"
                if h < 2
                else f'{yes} codesick in "" {yes} {entry[h]};'
            )
        if m < 2:
            printed.add(m)
        else:
            lines.append(f'{no} codesick in "" {no} {entry[m]};')
    lines += [f"{c} codesick out {c} * *;" for c in sorted(printed)]
    return " ".join(lines)
