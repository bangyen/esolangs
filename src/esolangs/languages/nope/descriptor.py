"""Runtime capabilities for Nope.."""

from esolangs.languages.nope.lifecycle import CAPABILITIES
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Nope.",
    RuntimeSpec(
        "nope",
        category="other",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    id="nope",
)
