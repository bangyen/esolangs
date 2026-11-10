"""Assert raising behavior against the runtime's outcome-based wire decoder."""

from esolangs.outcomes import ExecutionOutcome
from esolangs.results import ExecutionResult
from esolangs.runtime._isolated import _decode_outcome
from esolangs.runtime._proof import TerminationResult


def _decode(text: str, *, expired: bool) -> ExecutionResult | TerminationResult:
    response = _decode_outcome(text, expired=expired)
    return response.unwrap() if isinstance(response, ExecutionOutcome) else response
