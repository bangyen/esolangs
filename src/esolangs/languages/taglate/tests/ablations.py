"""Independent printable-nibble construction and its fixed-slot ablation."""

from typing import Literal

from esolangs.generation.helpers import _validate_truth_table, essential_inputs, read_at
from esolangs.languages.taglate.generator import _affine, _even_reduce, _with_discards


def _packed(t: str, n: int) -> str:
    # Four truth bits per printable nibble; six parked constants per input.
    leaves = 1 << (n - 2)
    vs = [
        sum(int(b) << i for i, b in enumerate(t[j : j + 4]))
        for j in range(0, len(t), 4)
    ]
    order = range(leaves - 1, -1, -1)
    ghosts = [[48, 0, 0, 0, 0, 0] for _ in range(n)]
    ghosts[-1] = [48, 1, 1, 0, 48, 0]
    seed = "".join(chr(c) for g in ghosts for c in g)
    seed += (
        "".join("\0" + chr(32 + vs[j]) for j in order) + chr(32) + "0" + chr(1) + chr(3)
    )
    pre = "heeeeee" * n + "e" * (2 * leaves + 4) + "beeeee" * n
    tail = "".join(
        _even_reduce(leaves >> level, 2 + 6 * level, 6 * n + 2)
        for level in range(n - 2)
    )
    labels = ["z", "x", "offset", "unused", "oneA", "KA"]
    for i in range(n):
        labels += [f"b{i}"] + [f"g{i}.{j}" for j in range(5)]
    names = {
        "x",
        "offset",
        "oneA",
        "KA",
        f"b{n - 2}",
        f"b{n - 1}",
        f"g{n - 1}.0",
        f"g{n - 1}.1",
        f"g{n - 1}.2",
        f"g{n - 1}.3",
    }
    parts = []
    # One complete FIFO pass discards unused cells and restores cyclic order.
    for x in labels:
        parts.append("e" if x in names else "f")
    labels = [x for x in labels if x in names]

    def rotate(x: str) -> None:
        nonlocal labels
        k = labels.index(x)
        parts.append("e" * k)
        labels = labels[k:] + labels[:k]

    def binary(x: str, y: str, op: str, z: str) -> None:
        nonlocal labels
        rotate(x)
        assert labels[1] == y, (labels, x, y)
        parts.append(op)
        labels = [*labels[2:], z]

    binary("x", "offset", "b", "x0")
    binary("KA", f"b{n - 2}", "c", "pA")
    binary("oneA", "pA", "a", "DA")
    binary("x0", "DA", "d", "x1")
    binary(f"b{n - 1}", f"g{n - 1}.0", "c", "pB")
    binary("pB", f"g{n - 1}.1", "a", "DB")
    binary("x1", "DB", "d", "q")
    rotate("q")
    assert labels == ["q", f"g{n - 1}.2", f"g{n - 1}.3"], labels
    parts.append("gyjjegzfai")
    return seed + "\n" + pre + tail + "".join(parts)


def _slots(t: str, n: int) -> str:
    """Original pair-reversed slots and its two-input tail."""
    seed = "0" * (2 * n + 4 * (1 << n) + 2)
    ordered = "".join(t[i : i + 2] for i in range((1 << n) - 2, -1, -2))
    prefix = (
        "hee" * n
        + "".join("bd" if b == "1" else "bb" for b in ordered)
        + "ee"
        + "be" * n
    )
    reduce = "".join(
        _even_reduce(1 << (n - level), 2 * level, 2 * n) for level in range(n - 1)
    )
    final = (
        "e" * 7
        + "gy"
        + "e" * 3
        + "gz"
        + "e" * 3
        + "gy"
        + "e" * 3
        + "gzffgy"
        + "e" * 4
        + "gzea"
        + "e" * 4
        + "i"
    )
    return seed + "\n" + prefix + reduce + "e" * 6 + "f" * (2 * n - 4) + "efef" + final


def ablate(table: str, rule: Literal["default", "packed_leaves"]) -> str:
    """Return the default construction or disable printable nibble leaves."""
    n = _validate_truth_table(table)
    if len(set(table)) == 1:
        return table[0] + "\n" + "h" * n + "i"
    used = essential_inputs(table, n)
    if len(used) < n:
        return _with_discards(ablate(read_at(table, used, n), rule), used, n)
    if n == 1:
        return _affine(table)
    return _slots(table, n) if rule == "packed_leaves" else _packed(table, n)
