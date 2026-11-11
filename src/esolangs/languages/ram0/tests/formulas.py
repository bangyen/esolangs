"""RAM0's base token count and unequal-half node cap."""

from esolangs.generation.decision import saturated_residual_levels


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Price the positional prefix geometrically, then the saturated tail."""
    saturated = saturated_residual_levels(n)
    positions = 1 << (n - saturated)
    nodes = positions - 1
    weighted = (saturated + 6) * positions - n - 6
    for h in range(1, saturated + 1):
        layer = (1 << (1 << h)) - (1 << (1 << (h - 1)))
        nodes += layer
        weighted += layer * (h + 4)
    return {"B": 8 + n * (n + 9) // 2 + weighted, "P": nodes}
