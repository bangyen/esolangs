"""Runtime and compiler capabilities for Whitespace."""

from esolangs.languages.whitespace.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec, VerbatimSourcePolicy


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.whitespace.generator", "whitespace_request"
        ),
        layout_width=False,
        shape=Shape.REDUCING,
        no_wrap="a line feed is a token, so a break changes the command it splits",
    )


LANGUAGE = LanguageDeclaration(
    "Whitespace",
    RuntimeSpec(
        "whitespace",
        source_policy=VerbatimSourcePolicy(),
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
        machine_preparation="prepare_machine",
        empty_program="Whitespace program is empty",
    ),
    backend=DeferredBackend(_backend),
)
