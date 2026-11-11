"""Written-workspace bounds, including post-halt finalization."""

from esolangs.generation.decision import saturated_residual_levels


def _tree_units(n: int) -> int:
    """Nodes plus repeated zero-edge pointers, excluding the final level."""
    if n <= 1:
        return 0
    saturated = saturated_residual_levels(n)
    depth = n - saturated - 1
    current = 1 << depth
    units = current - 1  # positional levels have two distinct children each
    for h in range(saturated, 0, -1):
        below = (1 << (1 << h)) - 2
        units += current + min(current, 2 * current - below)
        current = below
    return units


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Expose the shared tree count used in the workspace proof."""
    return {"S": _tree_units(n)}


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Identify a constant reader or use the shared tree count."""
    if not program.startswith("GOTO "):
        return {"C": 1, "I": int(program.split()[-2] == "INVERT"), "S": 0}
    return {"C": 0, "I": 0, "S": _tree_units(n)}
