"""Runtime and compiler capabilities for Fargo."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.fargo.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Fargo",
    RuntimeSpec(
        "fargo",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="the interpreter reads before the program starts",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.fargo.generator", "fargo_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.fargo.generator", "fargo_balance_request"
        ),
        no_wrap="each physical line is one command; expressions have no continuation",
    ),
    contract=BooleanContract(
        input_shape="row_index",
        note="Fargo reads one number whose bits are the inputs, so the "
        "committed input is the row index rather than a bit per line",
    ),
)
