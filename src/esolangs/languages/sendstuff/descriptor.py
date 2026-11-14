"""Runtime and compiler capabilities for SendStuff."""

from esolangs.languages.sendstuff.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import TokenWrapper
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    _wrap = TokenWrapper(r"[|<>!@]?[A-Za-z0-9_.%]+|[\s\S]")
    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.sendstuff.generator", "sendstuff_request"
        ),
        layout_width=False,
        wrap=_wrap,
    )


LANGUAGE = LanguageDeclaration(
    "SendStuff",
    RuntimeSpec(
        "sendstuff",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="an exhausted Input or InputNumber sends nothing, as the spec says",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
)
