"""Boolean-function generator for Forbin."""

from itertools import pairwise

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table, best_input_order


def forbin(truth_table: str) -> str:
    """Build a Forbin program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Forbin's ``in`` reads one bit (most significant first), so each input
    byte contributes 8 reads and only the last bit (the LSB, which is what
    distinguishes ``'0'`` from ``'1'``) is used.  A decision tree over those
    bits is laid out with the range-loop if-trick: ``for _:!b..b`` runs its
    body once when ``b`` is 1 (the ``return`` cuts the second iteration)
    and falls through when ``b`` is 0, so each node emits the 1-subtree then
    the 0-subtree and every leaf prints the result byte and returns.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.helpers.best_input_order`).
    The ``(in 0)`` reads stay in input order -- all ``8n`` of them -- so
    only the bit a ``for`` names moves.
    """
    return best_input_order(truth_table, _forbin_ordered)


_FORBIN_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


_FORBIN_RESERVED = {"for", "in", "main", "out", "return"}


def _forbin_name(index: int) -> str:
    """Return the ``index``th shortest non-keyword identifier."""
    base = len(_FORBIN_ALPHABET)
    candidate = 0
    while True:
        value = candidate + 1
        chars = []
        while value:
            value, digit = divmod(value - 1, base)
            chars.append(_FORBIN_ALPHABET[digit])
        name = "".join(reversed(chars))
        if name not in _FORBIN_RESERVED:
            if index == 0:
                return name
            index -= 1
        candidate += 1


def _forbin_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Forbin program; see :func:`forbin`."""
    n = _validate_truth_table(truth_table)

    lines: list[str] = ["main {"]
    bits = [""] * n
    depth_of = {stream: depth for depth, stream in enumerate(perm)}
    for i in range(n):
        depth = depth_of[i]
        # Deep levels are repeated exponentially more often in the emitted
        # tree, so allocate their eight input bits first.
        start = 8 * (n - 1 - depth)
        reads = [_forbin_name(start + j) for j in range(8)]
        lines.append(f"  {','.join(reads)} = (in 0);")
        bits[depth] = reads[7]

    # ``changes[i]`` counts value boundaries through entry ``i``.  An
    # interval is constant iff its endpoints see the same count, so every
    # node's fold test is O(1) after this one linear pass.
    changes = [0]
    for previous, current in pairwise(truth_table):
        changes.append(changes[-1] + (previous != current))

    def emit(level: int, row: int) -> None:
        end = row + 2 ** (n - level)
        if level == n or changes[row] == changes[end - 1]:
            byte = _ASCII_ZERO + int(truth_table[row])
            lines.append(f"  out {','.join(format(byte, '08b'))};")
            lines.append("  return 0;")
            return
        bit = bits[level]
        lines.append(f"  for _:!{bit}..{bit} {{")
        emit(level + 1, row + 2 ** (n - 1 - level))
        lines.append("  }")
        emit(level + 1, row)

    emit(0, 0)
    lines.append("}")
    return "\n".join(lines)
