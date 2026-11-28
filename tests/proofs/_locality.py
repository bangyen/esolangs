"""Worst sampled commands, for the floors of docs/proofs Execution locality."""

import esolangs
from tests.proofs.measurement import measure, tables


def worst_commands(name: str, n: int) -> int:
    """Return the most commands any sampled table's program takes on a row."""
    return max(
        measure(name, t, program=esolangs.generate(name, t))[0] for t in tables(name, n)
    )
