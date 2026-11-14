"""Runtime and compiler capabilities for Back."""

from esolangs.languages.back.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec

PAIR = ("-", "+")


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.registry._backend import BooleanBackend, TemplateSpec
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.back.generator", "back_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, TemplateLayout](
            "esolangs.languages.back.generator", "back_balance_request"
        ),
        no_wrap="the beam path and embedded input occupy fixed grid coordinates",
        template=TemplateSpec(pair=PAIR),
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
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
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_mode="dump",
        note="Back has no output instruction and dumps its tape at halt; "
        "the answer is cell n; earlier cells are input storage or scratch",
    ),
    example=Example(expected="1 0 0"),
)
