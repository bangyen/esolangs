"""Runtime and compiler capabilities for Forbin."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.forbin.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Forbin",
    RuntimeSpec(
        "forbin",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="variable_based",
        empty_program="Forbin program has no main function",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.forbin.generator", "forbin_request"
        ),
        layout_width=True,
        # Not a tree: one painted call argument per entry, halved down to the first.
        shape=Shape.LOOKUP,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.forbin.generator", "forbin_balance_request"
        ),
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
