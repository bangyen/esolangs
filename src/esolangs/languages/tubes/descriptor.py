"""Runtime and compiler capabilities for Tubes."""

from esolangs.languages.tubes.lifecycle import CAPABILITIES
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
            "esolangs.languages.tubes.generator", "tubes_request"
        ),
        layout=SourceLayout(
            no_wrap="a newline adds a grid row and moves every vertical path",
            grid=True,
        ),
        # One memory cell per entry of the essential inputs' table.
        shape=Shape.REDUCING,
    )


LANGUAGE = LanguageDeclaration(
    "Tubes",
    RuntimeSpec(
        "tubes",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        empty_program="no ▶ start",
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
)
