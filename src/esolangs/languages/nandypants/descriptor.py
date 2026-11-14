"""Runtime and compiler capabilities for Nandypants."""

from esolangs.languages.nandypants.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
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
            "esolangs.languages.nandypants.generator", "nandypants_request"
        ),
        layout_width=False,
        no_wrap="a line break inside a label would split one number into two",
    )


LANGUAGE = LanguageDeclaration(
    "Nandypants",
    RuntimeSpec(
        "nandypants",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
)
