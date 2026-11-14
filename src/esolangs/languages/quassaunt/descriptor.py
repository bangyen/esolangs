"""Runtime and compiler capabilities for Quassaunt."""

from esolangs.languages.quassaunt.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.wrap import wrap_space_delimited
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.quassaunt.generator", "quassaunt_request"
        ),
        layout_width=False,
        # Whitespace separates words and a word holds none, so break only there.
        wrap=wrap_space_delimited,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.quassaunt.generator", "quassaunt_balance_request"
        ),
    )


LANGUAGE = LanguageDeclaration(
    "Quassaunt",
    RuntimeSpec(
        "quassaunt",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
)
