"""Runtime and compiler capabilities for Flowchart."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.flowchart.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Flowchart",
    RuntimeSpec(
        "flowchart",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        split=True,
        eof="reads at input nodes, including the constant skip chain",
        empty_program="Flowchart program has no '( )' start node",
    ),
    backend=BooleanBackend(
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
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
