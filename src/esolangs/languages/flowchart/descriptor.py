"""Runtime and compiler capabilities for Flowchart."""

from esolangs.languages.flowchart.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.flowchart.generator", "flowchart_request"
        ),
        layout_width=True,
        # Not a tree: one deque push per entry.
        shape=Shape.LOOKUP,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.flowchart.generator", "flowchart_balance_request"
        ),
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
    "Flowchart",
    RuntimeSpec(
        "flowchart",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        source_policy=LineSourcePolicy(),
        eof="reads at input nodes, including the constant skip chain",
        empty_program="Flowchart program has no '( )' start node",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
