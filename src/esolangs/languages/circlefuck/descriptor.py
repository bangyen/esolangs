"""Runtime and compiler capabilities for Circlefuck."""

from esolangs.languages.circlefuck.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.circlefuck.generator", "circlefuck_request"
        ),
        layout_width=False,
        # A sum, not a tree: a lookup over the essential inputs only.
        shape=Shape.REDUCING,
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
    "Circlefuck",
    RuntimeSpec(
        "circlefuck",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
        eof="its input command is a no-op at EOF, as the spec says",
        empty_program="Circlefuck program cannot be empty",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
