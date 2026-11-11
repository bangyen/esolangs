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


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Identify the native constant or use the shared residual and line caps."""
    tokens = program.replace("$" * 6, "+J 0 0").replace("$", "0").split()
    if len(tokens) == 3 * (n + 1):
        return {"C": 1, "O": int(tokens[1] != "0"), "N": 0, "P": 0}
    return {"C": 0, "O": 0, "N": lines(n), "P": _nodes(n)}
