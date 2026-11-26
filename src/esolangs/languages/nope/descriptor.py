"""Runtime capabilities for Nope.."""

from esolangs.languages.nope.lifecycle import CAPABILITIES
from esolangs.registry._language import LanguageDeclaration
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = LanguageDeclaration(
    "Nope.",
    RuntimeSpec(
        "nope",
        reads_stdin=False,
        category="other",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ).with_native_plan(),
    id="nope",
)
