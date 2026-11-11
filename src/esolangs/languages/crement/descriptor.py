"""Runtime and compiler capabilities for Crement."""

from esolangs.languages.crement.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    Language,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.registry._backend import BooleanBackend, TemplateSpec
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.crement.generator", "crement_request"
        ),
        layout_width=True,
        same_layout=FunctionRef(
            "esolangs.languages.crement.generator",
            "_same_layout",
            ("template", "plain", "layout"),
        ),
        balance=OperationRef[BalanceRequest, TemplateLayout](
            "esolangs.languages.crement.generator", "crement_balance_request"
        ),
        no_wrap="jumps and patches name instruction numbers, so lines stay whole",
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.crement.generator",
                "crement_setters",
                ("template", "n"),
            )
        ),
    )


LANGUAGE = Language(
    "Crement",
    RuntimeSpec(
        "crement",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="program_based",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="Crement answers by termination: the tree's nodes patch a "
        "per-input tester's jump targets, and the row lands past the "
        "end (halts, 0) or on a self-jump (diverges, 1)",
    ),
    example=Example(expected=""),
)
