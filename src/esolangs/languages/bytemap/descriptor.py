"""Runtime and compiler capabilities for Bytemap."""

from esolangs.languages.bytemap.lifecycle import CAPABILITIES
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
            "esolangs.languages.bytemap.generator", "bytemap_request"
        ),
        layout_width=False,
        # Not a tree: the inputs index a table of five-byte print commands.
        shape=Shape.LOOKUP,
        no_wrap="a newline starts a new grid row",
    )


LANGUAGE = LanguageDeclaration(
    "Bytemap",
    RuntimeSpec(
        "bytemap",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        eof="every byte a read would write is FF",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
