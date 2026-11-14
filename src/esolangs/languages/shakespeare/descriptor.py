"""Runtime and compiler capabilities for Shakespeare."""

from esolangs.languages.shakespeare.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_space_delimited
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.shakespeare.generator", "shakespeare_request"
        ),
        layout_width=False,
        shape=Shape.LOOKUP,
        wrap=wrap_space_delimited,
    )


LANGUAGE = LanguageDeclaration(
    "Shakespeare",
    RuntimeSpec(
        "shakespeare",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
        empty_program="Shakespeare line 1: empty play",
    ),
    backend=DeferredBackend(_backend),
)
