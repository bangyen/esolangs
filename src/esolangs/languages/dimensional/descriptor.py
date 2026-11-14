"""Runtime and compiler capabilities for Dimensional."""

from esolangs.languages.dimensional.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.wrap import _dimensional
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.dimensional.generator", "dimensional_request"
        ),
        layout_width=True,
        # Not a tree: one painted cell per entry along dimension 1.
        shape=Shape.LOOKUP,
        wrap=_dimensional,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.dimensional.generator", "dimensional_balance_request"
        ),
    )


LANGUAGE = LanguageDeclaration(
    "Dimensional",
    RuntimeSpec(
        "dimensional",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
)
