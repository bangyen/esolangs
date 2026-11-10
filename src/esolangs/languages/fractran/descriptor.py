"""Runtime and compiler capabilities for FRACTRAN."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.languages.fractran.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

PAIR = ("0", "1")


LANGUAGE = Language(
    "FRACTRAN",
    RuntimeSpec(
        "fractran",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
        empty_program="a FRACTRAN program needs a starting value",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.fractran.generator", "fractran_request"
        ),
        layout_width=True,
        same_layout=FunctionRef(
            "esolangs.languages.fractran.generator",
            "_same_layout",
            ("template", "plain", "layout"),
        ),
        # Whitespace- or comma-separated tokens, and a break inside one would
        # change a number.
        wrap=wrap_space_delimited,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.fractran.generator", "fractran_balance_request"
        ),
        template=TemplateSpec(pair=PAIR),
    ),
    contract=BooleanContract(
        answer_mode="dump",
        answer_values=("1", "2"),
        note="FRACTRAN has neither input nor output: the inputs are the "
        "exponents of n primes in the starting value, and the answer "
        "is the value the run stops on -- 1 for a zero and 2 for a one",
    ),
    example=Example(expected="1"),
)
