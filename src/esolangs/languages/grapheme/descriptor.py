"""Runtime and compiler capabilities for Grapheme."""

from esolangs._dialect import DialectSchema
from esolangs.languages.grapheme.dialect import INTEGER_CONVERSIONS
from esolangs.languages.grapheme.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import BackendDefinition, DeferredBackend, Language
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.grapheme.generator", "grapheme_request"
        ),
        layout_width=False,
        wrap=wrap_chars,
    )


LANGUAGE = Language(
    "Grapheme",
    RuntimeSpec(
        "grapheme",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
        dialect=FunctionRef(
            "esolangs.languages.grapheme.dialect",
            "GraphemeDialect",
            ("integer_conversion",),
        ),
        dialect_schema=DialectSchema(
            "Grapheme",
            {"integer_conversion": INTEGER_CONVERSIONS},
            {"integer_conversion": "between_letters"},
        ),
    ),
    backend=DeferredBackend(_backend),
    # Each input line is normalized with ord(line[0]) - 65 and then zero is
    # mapped to 1; the second step is what makes 'A' a 1 -- ord('A') - 65 is
    # 0, so the subtraction alone says the opposite.
    contract=BooleanContract(
        alphabet=("%", "A"),
        note="input bits are spelled % and A: a line starting with A is a 1 "
        "and any other line a 0, so a 0/1 line reads as 0 and the program "
        "answers the all-zeros row; esolangs encode-inputs spells them",
    ),
)
