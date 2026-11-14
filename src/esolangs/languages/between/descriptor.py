"""Runtime and compiler capabilities for Between."""

from esolangs.languages.between.lifecycle import CAPABILITIES
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
            "esolangs.languages.between.generator", "between_request"
        ),
        layout_width=False,
        no_wrap="each line is one instruction and a break splits it",
    )


LANGUAGE = LanguageDeclaration(
    "Between",
    RuntimeSpec(
        "between",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
    ),
    backend=DeferredBackend(_backend),
)
