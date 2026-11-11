"""Runtime and compiler capabilities for INTERCAL."""

from esolangs.languages.intercal.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    Language,
)
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("#0", "#1")


TEMPLATE_CHAR = "@"


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.registry._backend import BooleanBackend, TemplateSpec
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.intercal.generator", "intercal_request"
        ),
        layout_width=True,
        same_layout=FunctionRef(
            "esolangs.languages.intercal.generator",
            "_same_layout",
            ("template", "_plain", "layout"),
        ),
        balance=OperationRef[BalanceRequest, TemplateLayout](
            "esolangs.languages.intercal.generator", "intercal_balance_request"
        ),
        template=TemplateSpec(pair=PAIR, char=TEMPLATE_CHAR),
    )


LANGUAGE = Language(
    "INTERCAL",
    RuntimeSpec(
        "intercal",
        category="variable_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
        empty_program="INTERCAL program is insufficiently or excessively polite (E099)",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_pattern=r"(?s)^(_\n|I)\n$",
        answer_values=("_\n", "I"),
        note="INTERCAL READ OUT prints a lone overbar for zero and I for one",
    ),
    example=Example(expected="_\n\n"),
)
