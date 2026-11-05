"""Runtime capabilities for Deadfish."""

from esolangs.languages.deadfish.lifecycle import CAPABILITIES
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Deadfish",
    RuntimeSpec(
        "deadfish",
        category="register_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    id="deadfish",
)
