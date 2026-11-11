"""A linear source ceiling, retaining the old deep diagram witness corpus."""

from esolangs.generation.helpers import short_name
from esolangs.languages.quassaunt.generator import _ALPHABET
from esolangs.languages.quassaunt.proof_formulas import node_cap
from tests.proofs._diagram_bounds import capped_level, worst_diagram


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Price the longest key using the emitter's bijective alphabet."""
    nodes = node_cap(n)
    width = len(short_name(nodes - 1, _ALPHABET))
    return {"W": width}


def witness(n: int) -> str:
    """Retain the former widest-ID diagram, exercising every deep arity."""
    return worst_diagram(
        n, lambda node, _: len(str(node)), 1 + len(str(capped_level(n)))
    )
