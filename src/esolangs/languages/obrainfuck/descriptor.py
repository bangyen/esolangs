"""Runtime and compiler capabilities for oBrainfuck."""

from esolangs.languages.obrainfuck.lifecycle import CAPABILITIES
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
            "esolangs.languages.obrainfuck.generator", "obrainfuck_request"
        ),
        layout_width=False,
        # Not a tree: the inputs index a table laid out on the tape.
        shape=Shape.LOOKUP,
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
    "oBrainfuck",
    RuntimeSpec(
        "obrainfuck",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
