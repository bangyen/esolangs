"""Runtime and compiler capabilities for Smallfuck."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.smallfuck.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Smallfuck",
    RuntimeSpec(
        "smallfuck",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.smallfuck.generator", "smallfuck_request"
        ),
        layout_width=True,
        same_layout=FunctionRef(
            "esolangs.languages.smallfuck.generator",
            "_same_layout",
            ("template", "plain", "layout"),
        ),
        wrap=wrap_chars,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.smallfuck.generator", "smallfuck_balance_request"
        ),
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.smallfuck.generator",
                "smallfuck_setters",
                ("template", "n"),
            )
        ),
    ),
    contract=BooleanContract(
        note="Smallfuck defines no I/O; this implementation prints final cell 2",
    ),
)
