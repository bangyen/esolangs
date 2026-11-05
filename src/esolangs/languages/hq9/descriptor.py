"""Runtime capabilities for HQ9+."""

from esolangs.languages.hq9.lifecycle import CAPABILITIES
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "HQ9+",
    RuntimeSpec(
        "hq9",
        category="register_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    id="hq9",
)
