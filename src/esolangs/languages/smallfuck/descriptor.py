"""Runtime and compiler capabilities for Smallfuck."""

from esolangs.languages.smallfuck.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, TemplateSpec
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.smallfuck.generator", "smallfuck_request"
        ),
        layout_width=True,
        same_layout=FunctionRef(
            "esolangs.languages.smallfuck.generator",
            "_same_layout",
            ("template", "plain", "layout"),
        ),
        wrap=wrap_chars,
        balance=OperationRef[BalanceRequest, TemplateLayout](
            "esolangs.languages.smallfuck.generator", "smallfuck_balance_request"
        ),
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.smallfuck.generator",
                "smallfuck_setters",
                ("template", "n"),
            )
        ),
    )


LANGUAGE = LanguageDeclaration(
    "Smallfuck",
    RuntimeSpec(
        "smallfuck",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="Smallfuck defines no I/O; this implementation prints final cell 2",
    ),
)
