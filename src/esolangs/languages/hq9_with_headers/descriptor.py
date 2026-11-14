"""Runtime and compiler capabilities for HQ9+ with headers."""

from esolangs.languages.hq9_with_headers.lifecycle import CAPABILITIES
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
            "esolangs.languages.hq9_with_headers.generator", "hq9_with_headers_request"
        ),
        layout_width=False,
        # Not a tree: the table is one decimal literal the reads divide down.
        shape=Shape.LOOKUP,
        no_wrap="a line break ends a header line; only a trailing \\ joins two",
    )


LANGUAGE = LanguageDeclaration(
    "HQ9+ with headers",
    RuntimeSpec(
        "hq9_with_headers",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="a read at EOF yields 0",
        empty_program=(
            "HQ9+ with headers: line 1: the source must start with '==== HEADER ===='"
        ),
    ),
    backend=DeferredBackend(_backend),
)
