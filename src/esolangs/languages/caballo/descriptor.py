"""Runtime and compiler capabilities for Caballo."""

from esolangs.languages.caballo.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.caballo.generator", "caballo_request"
        ),
        layout_width=False,
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
    "Caballo",
    RuntimeSpec(
        "caballo",
        category="stack_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
        eof="the whole input is read once as the initial stack; no read meets EOF",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"^(\[\]|\[1\])$",
        answer_values=("[]", "[1]"),
        note="Caballo reads its inputs as the initial stack, the first on "
        "top, and prints the surviving stack: [1] for one, [] for zero",
    ),
    example=Example(expected="[]"),
)
