"""The width sweep ``balance_qoibl`` approximates in closed form."""

from esolangs.generation.wrap import balance_score
from esolangs.languages.qoibl.generator import qoibl


def sweep_balance_qoibl(table: str, default: str) -> str:
    """Return the best wrap over every width up to the longest literal."""
    floor = max(len(token) for token in default.split())
    return min(
        [default, *(qoibl(table, width) for width in range(2, floor + 2))],
        key=balance_score,
    )
