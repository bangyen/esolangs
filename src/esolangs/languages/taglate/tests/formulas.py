"""Full-support literal-seed resource attainers."""

from esolangs.registry._certification import ProofFormula

FORMULAS: dict[str, ProofFormula] = {}


def resource_witness(n: int) -> str:
    """Keep every input essential, with nibble15 at the all-one prefix."""
    if n == 1:
        return "10"
    if n == 2:
        return "0111"
    return "0001" + "0" * ((1 << n) - 8) + "1111"
