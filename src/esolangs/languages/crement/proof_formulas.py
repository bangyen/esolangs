"""Snapshot-bit bounds."""

from esolangs.generation.decision import saturated_residual_levels


def lines(n: int) -> int:
    """The line maximum; named presets remove the old maxima below three."""
    if n <= 2:
        return 5 if n == 1 else 13
    return 3 * _nodes(n) + 2 * n + 3


def _nodes(n: int) -> int:
    if n <= 1:
        return n
    # Unequal halves saturate at the same positional cutoff as all
    # residuals. At the one-input tie both counts still give the same cap.
    saturated = saturated_residual_levels(n)
    prefix = (1 << (n - saturated)) - 1
    return prefix + sum(
        (1 << (1 << h)) - (1 << (1 << (h - 1))) for h in range(1, saturated + 1)
    )


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Use the same unequal-half cap as the workspace proof."""
    return {"P": _nodes(n)}


def _crement(n: int, _: str) -> int:
    """The whole program; P bounds the shared nodes, N the instructions."""
    bl = int.bit_length
    p = _nodes(n)
    m = lines(n)
    return (
        2 * bl(m)
        + 32
        + bl(2 * n + 3)
        + 2 * n * (10 + bl(m - 1))
        + p * (28 + 3 * bl(2 * n + 2) + 2 * bl(m - 2))
    )


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    tokens = p.replace("$" * 6, "+J 0 0").replace("$", "0").split()
    if len(tokens) == 3 * (n + 1):
        # The snapshot groups the untouched program with its changed cursor.
        return 0 if tokens[1] == "0" else 11 * n + 10 + 2 * (n + 1).bit_length()
    return _crement(n, p)
