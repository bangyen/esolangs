"""Runtime and compiler capabilities for thisthat."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.thisthat.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "thisthat",
    RuntimeSpec(
        "thisthat",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
        split=True,
        eof="an exhausted '◇' sends the spec's empty transfer",
        empty_program="thisthat needs at least one start node",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.thisthat.generator", "thisthat_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.thisthat.generator", "thisthat_balance_request"
        ),
        no_wrap="the H-tree's nodes and wires occupy fixed grid coordinates",
        grid=True,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
        ignores_whitespace=True,
        input_sets=True,
    ),
)
