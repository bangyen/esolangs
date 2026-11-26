r"""Q-BAL Boolean program generator: shift the table integer by the row.

One attachment, run once: ``N/2^(in\w+...+in)|2->out``.  ``N`` is the
integer whose bit ``r`` is row ``r`` of the table read at the essential
inputs; each ``in`` pops one input line, weighted by its place in that row,
so the exponent is the row and ``|2`` keeps the answer bit.  An ignored
input is read as ``in\0``.  A constant table prints ``b+0\(in+...+in)``.

Size:
    Theta(T) text: about 0.3T digits for ``N`` plus O(n^2) for the weights;
    n=4 parity: 34 chars, n=10 random 1847: 376 chars.

Decisions:
    The screening probe's decision tree (a relative branch ``; + k \ (in != 0)
    -> ;`` per node) emits 38,136 chars at n=10; the integer needs no branch.
    Every operator group here reads the same under the conventional order of
    operations, so the literal "^ \ / | + -" order is not load-bearing.
"""

from esolangs.generation.projection import InputProjection
from esolangs.generation.requests import GenerationRequest, TruthTable, project_inputs
from esolangs.runtime._program import Program
from esolangs.runtime.memory import format_integer


def q_bal(truth_table: str) -> str:
    """Build a Q-BAL program printing ``truth_table[row]`` for the inputs."""
    return _emit(project_inputs(TruthTable(truth_table)))


def _emit(projection: InputProjection) -> str:
    n, kept, table = projection
    if not kept:
        return f"{table[0]}+0\\({'+'.join(['in'] * n)})->out"
    terms = [
        "in" if weight == 1 else f"in\\{weight}"
        for weight in projection.weighted().weights
    ]
    number = format_integer(int(table[::-1], 2))
    return f"{number}/2^({'+'.join(terms)})|2->out"


def q_bal_request(request: GenerationRequest) -> Program:
    """Emit source through a typed backend request."""
    return _emit(project_inputs(request.truth_table))
