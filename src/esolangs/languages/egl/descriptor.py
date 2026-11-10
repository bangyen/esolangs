"""Runtime and compiler capabilities for EGL."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.egl.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "EGL",
    RuntimeSpec(
        "egl",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="grid_based",
        empty_program="EGL program must begin with 'width,height:'",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.egl.generator", "egl_request"
        ),
        layout_width=True,
        # Not a tree: one painted grid cell per entry, walked to by weighted guards.
        shape=Shape.LOOKUP,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.egl.generator", "egl_balance_request"
        ),
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
