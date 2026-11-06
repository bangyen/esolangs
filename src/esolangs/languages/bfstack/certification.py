"""Language-owned verification policy."""

from typing import Any

from esolangs.registry._certification import CertificationSpec, Payload


def _payload(state: Any) -> Payload:
    """Split out the data stack, loop stack and pc; the cursor is I/O state."""
    data, control, pc, _cursor = state
    return data, control, pc, 0


CERTIFICATION = CertificationSpec(payload=_payload)
