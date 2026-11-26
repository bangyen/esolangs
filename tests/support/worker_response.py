"""Exercise the runtime's worker response decoders."""

from collections.abc import Hashable
from typing import Any

from esolangs.outcomes import ExecutionOutcome
from esolangs.results import ExecutionResult
from esolangs.runtime._proof import TerminationResult
from esolangs.runtime._snapshot_wire import _state_wire
from esolangs.runtime._worker_response import _decode_outcome


def _decode(text: str, *, expired: bool) -> ExecutionResult | TerminationResult:
    response = _decode_outcome(text, expired=expired)
    return response.unwrap() if isinstance(response, ExecutionOutcome) else response


def owned_snapshot_with_payload(state: Hashable, payload: Hashable) -> Any:
    """Replace an owned payload while reserving definition zero for its owner."""
    packet = _state_wire(state)
    wrapped = _state_wire((payload,))
    packet["define"][1]["owned"]["value"] = wrapped["define"][1]["tuple"][0]
    return packet
