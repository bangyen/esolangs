"""Runtime and compiler capabilities for RAM0."""

from esolangs.languages.ram0.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("Z", "A")


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.generation.wrap import wrap_space_delimited
    from esolangs.registry._backend import BooleanBackend, TemplateSpec
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.ram0.generator", "ram0_request"
        ),
        layout_width=True,
        same_layout=FunctionRef(
            "esolangs.generation.helpers",
            "same_token_layout",
            ("template", "plain", "_layout"),
        ),
        # Multi-character tokens (``vs``, ``0b1``, ``L C 19``); space is the
        # only safe break.
        wrap=wrap_space_delimited,
        balance=OperationRef[BalanceRequest, TemplateLayout](
            "esolangs.languages.ram0.generator", "ram0_balance_request"
        ),
        template=TemplateSpec(pair=PAIR),
    )


LANGUAGE = LanguageDeclaration(
    "RAM0",
    RuntimeSpec(
        "ram0",
        category="register_based",
        reads_stdin=False,
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"z: (\d+)",
        note="RAM0 has no output instruction and dumps its whole state "
        "at halt; the answer is the 'z' register",
    ),
    example=Example(expected="z: 0\nn: 0\nram: {\n    1: 0,\n    0: 1\n}"),
)
