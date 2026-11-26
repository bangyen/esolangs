"""Runtime and compiler capabilities for Collatz Multiverse."""

from esolangs.languages.collatz_multiverse.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, ConstructedLayout
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.collatz_multiverse.generator",
            "collatz_multiverse_request",
        ),
        layout=ConstructedLayout(
            layout_balance=True,
            no_wrap="each line is one complete register assignment",
        ),
    )


LANGUAGE = LanguageDeclaration(
    "Collatz Multiverse",
    RuntimeSpec(
        "collatz_multiverse",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
)
