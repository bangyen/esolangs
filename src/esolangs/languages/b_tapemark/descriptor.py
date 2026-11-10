"""Runtime and compiler capabilities for B-tapemark."""

from esolangs._dialect import DialectSchema
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.b_tapemark.dialect import SWAP_MARKERS, validate_swap_marker
from esolangs.languages.b_tapemark.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program


def _dialect(swap_marker: str = "new") -> None:
    """Validate which grid's marker moves after a swap."""
    validate_swap_marker(swap_marker)


LANGUAGE = Language(
    "B-tapemark",
    RuntimeSpec(
        "b_tapemark",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="grid_based",
        dialect=_dialect,
        dialect_schema=DialectSchema(
            "B-tapemark", {"swap_marker": SWAP_MARKERS}, {"swap_marker": "new"}
        ),
        empty_program="B-tapemark program needs exactly one start marker",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.b_tapemark.generator", "b_tapemark_request"
        ),
        layout_width=True,
        # Not a tree: the table copied onto the grid, one mark per row.
        shape=Shape.LOOKUP,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.b_tapemark.generator", "b_tapemark_balance_request"
        ),
        grid=True,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
