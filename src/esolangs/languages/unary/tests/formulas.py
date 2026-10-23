"""Unary's peak written state: the programs a nine-command budget admits."""

bl = int.bit_length

#: (k, t): a program of n + k commands holds t bits of tape and pointer at its
#: peak.  Constant 0 reads n cells into one (k = 0, 8); the last input as-is or
#: negated adds ``[]`` and ``+[]`` (k = 2, 3; one 255 cell); any other input
#: moves to a second cell, tape (0, 255) (k = 4: 1 pointer bit + 9) or, negated,
#: (255, 255) (k = 5: 1 + 16).
_SHAPES = ((0, 8), (2, 8), (3, 8), (4, 10), (5, 17))


def workspace(n: int, _: str) -> int:
    """Peak instruction index, input count, tape and pointer, over the shapes.

    ``8**9`` is under the 256 Mi cap, ``8**10`` over it: at most nine commands,
    so a shape needs n + k <= 9.  Any other table reads every input in a
    decision tree or the AND chain, 4n - 2 or 5n - 2 commands.
    """
    return max(t + bl(n) + bl(n + k) for k, t in _SHAPES if n + k <= 9)


FORMULAS = {"workspace": (workspace, True, (2, 3, 4, 5, 6, 7, 8))}
