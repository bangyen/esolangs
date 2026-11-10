"""Runtime and compiler capabilities for Super SNUSP."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.super_snusp.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Super SNUSP",
    RuntimeSpec(
        "super_snusp",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
        split=True,
        empty_program="Super SNUSP program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.super_snusp.generator", "super_snusp_request"
        ),
        layout_width=True,
        # A sum, not a tree: a lookup over the essential inputs only.
        shape=Shape.REDUCING,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.super_snusp.generator", "super_snusp_balance_request"
        ),
        no_wrap="a row is a grid row; a break moves code, it does not reflow",
        grid=True,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
