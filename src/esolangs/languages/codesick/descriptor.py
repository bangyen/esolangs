"""Runtime and compiler capabilities for Codesick."""

from esolangs.languages.codesick.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_space_delimited
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.codesick.generator", "codesick_request"
        ),
        layout_width=False,
        # An argument holds no whitespace, so break only between arguments.
        wrap=wrap_space_delimited,
    )


LANGUAGE = LanguageDeclaration(
    "Codesick",
    RuntimeSpec(
        "codesick",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="the whole input is read once to replace every `in`; no read meets EOF",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
)
