"""Runtime and compiler capabilities for Flipscript."""

from esolangs.languages.flipscript.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.flipscript.generator", "flipscript_request"
        ),
        layout_width=False,
        no_wrap="each line is one statement and a break splits it",
    )


LANGUAGE = LanguageDeclaration(
    "Flipscript",
    RuntimeSpec(
        "flipscript",
        category="other",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        empty_program="no start statement",
    ),
    backend=DeferredBackend(_backend),
)
