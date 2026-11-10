"""Runtime and compiler capabilities for REFRACTRAN."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.languages.refractran.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

PAIR = ("0", "1")


LANGUAGE = Language(
    "REFRACTRAN",
    RuntimeSpec(
        "refractran",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
        empty_program="REFRACTRAN needs an initial integer",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.refractran.generator", "refractran_request"
        ),
        layout_width=True,
        wrap=wrap_space_delimited,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.refractran.generator", "refractran_balance_request"
        ),
        template=TemplateSpec(pair=PAIR),
    ),
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"([01])$",
        note="Inputs are ordered prime exponents in the initial integer; "
        "the final binary state ends in the answer bit.",
    ),
    example=Example(expected_compared=False),
)
