"""Runtime and compiler capabilities for Back."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.back.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec
from esolangs.runtime._program import Program

PAIR = ("-", "+")


LANGUAGE = Language(
    "Back",
    RuntimeSpec(
        "back",
        category="tape_based",
        source_policy=LineSourcePolicy(),
        empty_program="Back program cannot be empty",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.back.generator", "back_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.back.generator", "back_balance_request"
        ),
        no_wrap="the beam path and embedded input occupy fixed grid coordinates",
        template=TemplateSpec(pair=PAIR),
        grid=True,
    ),
    contract=BooleanContract(
        answer_mode="dump",
        note="Back has no output instruction and dumps its tape at halt; "
        "the answer is cell n; earlier cells are input storage or scratch",
    ),
    example=Example(expected="1 0 0"),
)
