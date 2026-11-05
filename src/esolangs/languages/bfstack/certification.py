"""Language-owned verification policy."""

from esolangs.registry._certification import CertificationSpec
from esolangs.registry._functions import FunctionRef

CERTIFICATION = CertificationSpec(
    payload=FunctionRef("esolangs.languages.bfstack.generator", "_payload", ("state",)),
)
