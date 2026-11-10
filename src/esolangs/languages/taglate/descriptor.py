"""Runtime and compiler capabilities for Taglate."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.taglate.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Taglate",
    RuntimeSpec(
        "taglate",
        category="queue_based",
        split=True,
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.taglate.generator", "taglate_request"
        ),
        layout_width=True,
        # Both concatenate before tokenizing (Taglate after the queue seed; A
        # Painter Ant drops whitespace), so no break can land inside a command.
        wrap=FunctionRef(
            "esolangs.languages.taglate.wrapping", "_taglate", ("program", "width")
        ),
        wrap_multiline=True,
        same_layout=FunctionRef(
            "esolangs.languages.taglate.wrapping",
            "same_layout",
            ("template", "plain", "_layout"),
        ),
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.taglate.generator", "taglate_balance_request"
        ),
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
