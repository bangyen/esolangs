"""Runtime and compiler capabilities for SwitchCase."""

from esolangs.languages.switchcase.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
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
            "esolangs.languages.switchcase.generator", "switchcase_request"
        ),
        layout_width=False,
        shape=Shape.TREE,
        no_wrap="a line is one arm, and a case's arms follow its $ line",
    )


LANGUAGE = LanguageDeclaration(
    "SwitchCase",
    RuntimeSpec(
        "switchcase",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="variable_based",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
)
