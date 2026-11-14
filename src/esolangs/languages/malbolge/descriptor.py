"""Runtime and compiler capabilities for Malbolge."""

from esolangs.exceptions import GeneratorCapError
from esolangs.languages.malbolge.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime.source_hints import with_hint

_DIGITS_N = 16
MAX_INPUTS = _DIGITS_N


def input_cap_error(inputs: int) -> GeneratorCapError:
    """Explain the unconditional store limit and the conditional extension."""
    storage = (
        "every row pair owns a cell, and seventeen inputs would need "
        "65,536 of the store's 59,049"
    )
    detail = (
        "seventeen is built only for a table that ignores an input or "
        "is constant on Hamming-weight classes, and this one does neither; "
        if inputs == MAX_INPUTS + 1
        else ""
    )
    return with_hint(
        GeneratorCapError(
            f"Malbolge builds at most {_DIGITS_N} inputs, got {inputs}: "
            f"{detail}{storage}"
        ),
        (
            "use fewer inputs or check another generator's "
            "limits; width cannot enlarge Malbolge's store"
        ),
    )


def check_arity(inputs: int) -> None:
    """Refuse beyond the largest arity the store can accommodate."""
    if inputs > MAX_INPUTS + 1:
        raise input_cap_error(inputs)


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        max_inputs=MAX_INPUTS + 1,
        arity_guard=check_arity,
        restrictions=(
            "seventeen inputs only for a table that ignores an input "
            "or is constant on Hamming-weight classes"
        ),
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.malbolge.generator", "malbolge_request"
        ),
        layout_width=False,
        # Not a tree: straight-line code into the fixed store.
        shape=Shape.LOOKUP,
        # Loader whitespace is discarded before assigning memory addresses.
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
    "Malbolge",
    RuntimeSpec(
        "malbolge",
        category="program_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        eof="an exhausted read is the value 59048, not an error",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="the answer is one character and is printed with no newline",
        input_shape="char_stream",
    ),
)
