"""Runtime and compiler capabilities for Chicken."""

from esolangs.languages.chicken.lifecycle import CAPABILITIES
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
            "esolangs.languages.chicken.generator", "chicken_request"
        ),
        layout_width=False,
        shape=Shape.LOOKUP,
        no_wrap="a line break is the instruction boundary and a blank line is a cell",
    )


LANGUAGE = LanguageDeclaration(
    "Chicken",
    RuntimeSpec(
        "chicken",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
        eof="a short input is a shorter string; a missing bit is not 1, so reads 0",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
        note="Chicken's input is one string; input[i] is bit i",
    ),
)
