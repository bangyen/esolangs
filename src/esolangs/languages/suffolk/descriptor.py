"""Runtime and compiler capabilities for Suffolk."""

from esolangs.languages.suffolk.lifecycle import CAPABILITIES
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
            "esolangs.languages.suffolk.generator", "suffolk_request"
        ),
        layout_width=False,
        # Both routes project to the essential inputs.
        shape=Shape.REDUCING,
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
    "Suffolk",
    RuntimeSpec(
        "suffolk",
        completion_entrypoint="_execute",
        machine_preparation="prepare_machine",
        capabilities=CAPABILITIES,
        category="tape_based",
        # Reads until the input runs out and treats that as its stop, which is
        # how its generated programs terminate at all.
        eof="reads to exhaustion, so EOF is the halt",
        empty_program="Suffolk program cannot be empty",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
