"""Runtime and compiler capabilities for ROTfuck."""

from esolangs.generation.wrap import wrap_chars
from esolangs.languages.rotfuck.dialect import ROTATIONS, validate_rotation
from esolangs.languages.rotfuck.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec


def _dialect(rotation: str = "backward") -> None:
    """Validate which way ROTfuck's command cycle turns."""
    validate_rotation(rotation)


LANGUAGE = Language(
    "ROTfuck",
    RuntimeSpec(
        "rotfuck",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
        dialect=_dialect,
        dialect_values={"rotation": ROTATIONS},
        dialect_defaults={"rotation": "backward"},
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.rotfuck.generator",
            "rotfuck",
            ("truth_table", "rotation"),
        ),
        # A sum, not a tree: a lookup over the essential inputs only.
        shape=Shape.REDUCING,
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
