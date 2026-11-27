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
MAX_INPUTS = 17


def check_arity(inputs: int) -> None:
    """Refuse beyond the packed decoder's seventeen inputs."""
    if inputs > MAX_INPUTS:
        raise with_hint(
            GeneratorCapError(
                f"Malbolge builds at most {MAX_INPUTS} inputs (got {inputs})"
            ),
            "use fewer inputs or check another generator's limits",
        )


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, Shape, SourceLayout
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        max_inputs=MAX_INPUTS,
        arity_guard=check_arity,
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.malbolge.generator", "malbolge_request"
        ),
        layout=SourceLayout(
            wrap=wrap_chars,
        ),
        # Not a tree: straight-line code into the fixed store.
        shape=Shape.LOOKUP,
        # Loader whitespace is discarded before assigning memory addresses.
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
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="the answer is one character and is printed with no newline",
        input_shape="char_stream",
    ),
)
