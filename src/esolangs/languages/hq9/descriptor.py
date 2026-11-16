"""Runtime capabilities for HQ9+."""

from esolangs.languages.hq9.lifecycle import CAPABILITIES
from esolangs.registry._language import LanguageDeclaration
from esolangs.runtime._definition import RuntimeSpec, VerbatimSourcePolicy

LANGUAGE = LanguageDeclaration(
    "HQ9+",
    RuntimeSpec(
        "hq9",
        source_policy=VerbatimSourcePolicy(),  # Q reproduces its source.
        reads_stdin=False,
        category="register_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    id="hq9",
)
