"""Runtime and compiler capabilities for ArrowQueue."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.arrowqueue.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

PAIR = (".", "~")


LANGUAGE = Language(
    "ArrowQueue",
    RuntimeSpec(
        "arrowqueue",
        category="grid_based",
        split=True,
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.arrowqueue.generator", "arrowqueue_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.arrowqueue.generator", "arrowqueue_balance_request"
        ),
        no_wrap="the queue and decision tree occupy fixed grid coordinates",
        template=TemplateSpec(pair=PAIR),
        grid=True,
    ),
    contract=BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="ArrowQueue answers by termination -- it halts for a 0 result "
        "and loops forever for a 1, so only the halting branch is "
        "committed.  The headings printed are its interpreter-only "
        "queue dump, which the verdict does not read: the answer is "
        "that the program halted at all",
    ),
    example=Example(expected=""),
)
