"""A linear source ceiling, retaining the old deep diagram witness corpus."""

from esolangs.generation.helpers import short_name
from esolangs.languages.quassaunt.generator import _ALPHABET
from esolangs.languages.quassaunt.proof_formulas import node_cap
from tests.proofs._diagram_bounds import capped_level, worst_diagram


def _chars(n: int, _: str) -> int:
    """At most N bodies/keys, fixed helper/startup, and two fillers per input."""
    nodes = node_cap(n)
    width = len(short_name(nodes - 1, _ALPHABET))
    # A triple costs at most 134+4u characters; 170 leaves room for every
    # node kind. The helper, [] triple, dummy and start cost below 400+u.
    return nodes * (170 + 4 * width) + 400 + width + 6 * n


def witness(n: int) -> str:
    """Retain the former widest-ID diagram, exercising every deep arity."""
    return worst_diagram(
        n, lambda node, _: len(str(node)), 1 + len(str(capped_level(n)))
    )
