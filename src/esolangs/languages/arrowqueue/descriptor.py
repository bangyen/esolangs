"""Runtime and compiler capabilities for ArrowQueue."""

from esolangs.languages.arrowqueue.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec

PAIR = (".", "~")


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.registry._backend import BooleanBackend, TemplateSpec
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.arrowqueue.generator", "arrowqueue_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, TemplateLayout](
            "esolangs.languages.arrowqueue.generator", "arrowqueue_balance_request"
        ),
        no_wrap="the queue and decision tree occupy fixed grid coordinates",
        template=TemplateSpec(pair=PAIR),
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
    "ArrowQueue",
    RuntimeSpec(
        "arrowqueue",
        category="grid_based",
        source_policy=LineSourcePolicy(),
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
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
