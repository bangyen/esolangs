"""Runtime and compiler capabilities for CV(N)(C)."""

from esolangs.languages.cvnc.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.cvnc.generator", "cvnc_request"
        ),
        layout_width=False,
        # LF-only source-format deviation: discard breaks before parsing or addressing.
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
    "CV(N)(C)",
    RuntimeSpec(
        "cvnc",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        empty_program="program is empty",
    ),
    # The parentheses mark optional slots; the language is written as one word.
    id="cvnc",
    backend=DeferredBackend(_backend),
)
