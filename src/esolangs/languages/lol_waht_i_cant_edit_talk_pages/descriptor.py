"""Runtime and compiler capabilities for lol waht i cant edit talk pages."""

from esolangs.languages.lol_waht_i_cant_edit_talk_pages.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.lol_waht_i_cant_edit_talk_pages.generator",
            "lol_waht_i_cant_edit_talk_pages_request",
        ),
        layout_width=False,
        no_wrap="every statement is one line, so a break splits a command",
    )


LANGUAGE = LanguageDeclaration(
    "lol waht i cant edit talk pages",
    RuntimeSpec(
        "lol_waht_i_cant_edit_talk_pages",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="variable_based",
    ),
    backend=DeferredBackend(_backend),
)
