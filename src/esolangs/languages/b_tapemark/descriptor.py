"""Runtime and compiler capabilities for B-tapemark."""

from esolangs.languages.b_tapemark.dialect import SWAP_MARKERS, validate_swap_marker
from esolangs.languages.b_tapemark.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec


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
        dialect_values={"swap_marker": SWAP_MARKERS},
        dialect_defaults={"swap_marker": "new"},
        empty_program="B-tapemark program needs exactly one start marker",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.b_tapemark.generator",
            "b_tapemark",
            ("truth_table", "width", "swap_marker"),
        ),
        # Not a tree: the table copied onto the grid, one mark per row.
        shape=Shape.LOOKUP,
        balance=FunctionRef(
            "esolangs.languages.b_tapemark.generator",
            "_balance",
            ("table", "default", "swap_marker"),
        ),
        grid=True,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
