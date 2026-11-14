"""Runtime and compiler capabilities for Painfuck."""

from esolangs.languages.painfuck.lifecycle import CAPABILITIES
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
            "esolangs.languages.painfuck.generator", "painfuck_request"
        ),
        layout_width=False,
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
    "Painfuck",
    RuntimeSpec(
        "painfuck",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
    ),
    backend=DeferredBackend(_backend),
)
