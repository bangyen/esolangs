"""Runtime and compiler capabilities for moar cheese :3."""

from esolangs.languages.moar_cheese_3.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("n", "y")


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.registry._backend import BooleanBackend, Shape, TemplateSpec
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.moar_cheese_3.generator", "moar_cheese_3_request"
        ),
        layout_width=False,
        # Input bits filter a queued table; no tree of residuals.
        shape=Shape.LOOKUP,
        no_wrap="a break inside ( ) or an input slot's ( ) changes it; balance folds",
        template=TemplateSpec(pair=PAIR),
        balance=OperationRef[BalanceRequest, TemplateLayout](
            "esolangs.languages.moar_cheese_3.generator",
            "moar_cheese_3_balance_request",
        ),
    )


LANGUAGE = LanguageDeclaration(
    "moar cheese :3",
    RuntimeSpec(
        "moar_cheese_3",
        reads_stdin=False,
        category="queue_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="Inputs are embedded as n or y; the final queue is the answer.",
    ),
)
