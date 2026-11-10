"""Runtime and compiler capabilities for Underload."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.underload.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Underload",
    RuntimeSpec(
        "underload",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.underload.generator", "underload_request"
        ),
        layout_width=True,
        same_layout=FunctionRef(
            "esolangs.languages.underload.generator",
            "_same_layout",
            ("template", "plain", "layout"),
        ),
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.underload.generator", "underload_balance_request"
        ),
        no_wrap="a break inside a pushed element changes the string it contains",
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.underload.generator",
                "underload_setters",
                ("template", "n"),
            )
        ),
    ),
    contract=BooleanContract(),
)
