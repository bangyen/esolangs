"""Runtime and compiler capabilities for Freestajlo."""

from esolangs.languages.freestajlo.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec

_UNIT = r'"[^"]*"|\'[\s\S]|\d+|[\s\S]'


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import TokenWrapper
    from esolangs.registry._backend import BooleanBackend, Shape, SourceLayout
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.freestajlo.generator", "freestajlo_request"
        ),
        layout=SourceLayout(
            layout_balance=True,
            wrap=TokenWrapper(_UNIT),
        ),
        shape=Shape.LOOKUP,
    )


LANGUAGE = LanguageDeclaration(
    "Freestajlo",
    RuntimeSpec(
        "freestajlo",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
        eof="an exhausted ',' is the spec's -1, an exhausted ';' its 0",
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
)
