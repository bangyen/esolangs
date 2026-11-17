"""Runtime and compiler capabilities for artppeice."""

from esolangs.languages.artppeice.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.artppeice.generator", "artppeice_request"
        ),
        layout_width=False,
        # One table word per entry of the essential inputs' table.
        shape=Shape.REDUCING,
        no_wrap="each line is one instruction and a break splits it",
    )


LANGUAGE = LanguageDeclaration(
    "artppeice",
    RuntimeSpec(
        "artppeice",
        category="queue_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        empty_program="no instructions",
    ),
    backend=DeferredBackend(_backend),
)
