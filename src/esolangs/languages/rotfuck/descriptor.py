"""Runtime and compiler capabilities for ROTfuck."""

from esolangs._dialect import DialectSchema
from esolangs.languages.rotfuck.dialect import ROTATIONS, validate_rotation
from esolangs.languages.rotfuck.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _dialect(rotation: str = "backward") -> None:
    """Validate which way ROTfuck's command cycle turns."""
    validate_rotation(rotation)


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.rotfuck.generator", "rotfuck_request"
        ),
        layout_width=False,
        # A sum, not a tree: a lookup over the essential inputs only.
        shape=Shape.REDUCING,
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
    "ROTfuck",
    RuntimeSpec(
        "rotfuck",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
        dialect=_dialect,
        dialect_schema=DialectSchema(
            "ROTfuck", {"rotation": ROTATIONS}, {"rotation": "backward"}
        ),
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
