"""Language-owned verification policy."""

from typing import Any

from esolangs.registry._certification import CertificationSpec, Payload


def _payload(state: Any) -> Payload:
    """Split out memory, mutable code included, and pc; no control stack."""
    data, pc, _cursor = state
    return data, (), pc, 0


CERTIFICATION = CertificationSpec(payload=_payload)
