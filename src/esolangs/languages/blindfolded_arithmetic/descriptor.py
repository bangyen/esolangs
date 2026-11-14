"""Runtime and compiler capabilities for Blindfolded Arithmetic."""

from esolangs.languages.blindfolded_arithmetic.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.blindfolded_arithmetic.generator",
            "blindfolded_arithmetic_request",
        ),
        layout_width=False,
        wrap=FunctionRef(
            "esolangs.languages.blindfolded_arithmetic.generator",
            "_wrap",
            ("program", "width"),
        ),
        # No flow control: the table is data, indexed by arithmetic, not a tree.
        shape=Shape.LOOKUP,
    )


LANGUAGE = LanguageDeclaration(
    "Blindfolded Arithmetic",
    RuntimeSpec(
        "blindfolded_arithmetic",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
        empty_program="a Blindfolded Arithmetic program needs at least one instruction",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="row_number",
        note="the input must be a positive integer, so the committed input is "
        "the row index plus one",
    ),
)
