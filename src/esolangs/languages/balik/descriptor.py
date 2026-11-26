"""Runtime and compiler capabilities for Balik."""

from esolangs.languages.balik.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape, SourceLayout
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.balik.generator", "balik_request"
        ),
        layout=SourceLayout(
            no_wrap="a newline adds a grid row and moves every vertical path",
        ),
        shape=Shape.TREE,
    )


LANGUAGE = LanguageDeclaration(
    "Balik",
    RuntimeSpec(
        "balik",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="grid_based",
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
)
