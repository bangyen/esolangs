"""Runtime and compiler capabilities for NQ."""

from esolangs._dialect import DialectSchema
from esolangs.languages.nq.dialect import DEFAULT_GUARD_BINDING, GUARD_BINDINGS
from esolangs.languages.nq.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
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
            "esolangs.languages.nq.generator", "nq_request"
        ),
        layout_width=False,
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
    "NQ",
    RuntimeSpec(
        "nq",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="queue_based",
        dialect=FunctionRef(
            "esolangs.languages.nq.interpreter", "guard_dialect", ("guard_binding",)
        ),
        dialect_schema=DialectSchema(
            "NQ",
            {"guard_binding": GUARD_BINDINGS},
            {"guard_binding": DEFAULT_GUARD_BINDING},
        ),
        machine_preparation="prepare_machine",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
        answer_pattern="([ #])",
        answer_values=(" ", "#"),
        note="The whole output is a space for false or # for true.",
        ignores_whitespace=True,
    ),
    example=Example(expected=" "),
)
