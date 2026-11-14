"""Runtime and compiler capabilities for thisthat."""

from esolangs.languages.thisthat.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.thisthat.generator", "thisthat_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.thisthat.generator", "thisthat_balance_request"
        ),
        no_wrap="the H-tree's nodes and wires occupy fixed grid coordinates",
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
    "thisthat",
    RuntimeSpec(
        "thisthat",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
        source_policy=LineSourcePolicy(),
        eof="an exhausted '◇' sends the spec's empty transfer",
        empty_program="thisthat needs at least one start node",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
        ignores_whitespace=True,
        input_sets=True,
    ),
)
