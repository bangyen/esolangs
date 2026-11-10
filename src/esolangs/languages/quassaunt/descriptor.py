"""Runtime and compiler capabilities for Quassaunt."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.languages.quassaunt.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Quassaunt",
    RuntimeSpec(
        "quassaunt",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.quassaunt.generator", "quassaunt_request"
        ),
        layout_width=False,
        # Whitespace separates words and a word holds none, so break only there.
        wrap=wrap_space_delimited,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.quassaunt.generator", "quassaunt_balance_request"
        ),
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
