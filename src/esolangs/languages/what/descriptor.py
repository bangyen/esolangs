"""Runtime and compiler capabilities for What!?."""

from esolangs.languages.what.lifecycle import CAPABILITIES
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

    _wrap = TokenWrapper(r'\[(?:\d+>|"[01]+":)|\d+|[?!]+|[\s\S]')
    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.what.generator", "what_request"
        ),
        layout_width=False,
        # Whitespace only separates tokens, so a newline between two is harmless.
        wrap=_wrap,
    )


LANGUAGE = LanguageDeclaration(
    "What!?",
    RuntimeSpec(
        "what",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        eof="a read at EOF yields 0",
    ),
    backend=DeferredBackend(_backend),
)
