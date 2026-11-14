"""Runtime and compiler capabilities for Bleh."""

from esolangs.languages.bleh.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec

_TOKEN = r'"[^\"]*"|::|\w+|[\s\S]'


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import TokenWrapper
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.bleh.generator", "bleh_request"
        ),
        layout_width=False,
        wrap=TokenWrapper(_TOKEN),
    )


LANGUAGE = LanguageDeclaration(
    "Bleh",
    RuntimeSpec(
        "bleh",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="an exhausted io::next() is the empty bitstring",
        underfed_raises=True,
        empty_program="a Bleh program needs a main function",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
)
