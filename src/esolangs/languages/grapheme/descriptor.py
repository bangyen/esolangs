"""Runtime and compiler capabilities for Grapheme."""

from esolangs.generation.wrap import wrap_chars
from esolangs.languages.grapheme.interpreter import INTEGER_CONVERSIONS
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Grapheme",
    RuntimeSpec(
        "grapheme",
        category="stack_based",
        dialect=FunctionRef(
            "esolangs.languages.grapheme.interpreter",
            "GraphemeDialect",
            ("integer_conversion",),
        ),
        dialect_values={"integer_conversion": INTEGER_CONVERSIONS},
        dialect_defaults={"integer_conversion": "between_letters"},
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.grapheme.generator",
            "grapheme",
            ("truth_table", "integer_conversion"),
        ),
        wrap=wrap_chars,
    ),
    # Each input line is normalized with ord(line[0]) - 65 and then zero is
    # mapped to 1; the second step is what makes 'A' a 1 -- ord('A') - 65 is
    # 0, so the subtraction alone says the opposite.
    contract=BooleanContract(
        alphabet=("%", "A"),
        note="input bits are spelled % and A: a line starting with A is a 1 "
        "and any other line a 0, so a 0/1 line reads as 0 and the program "
        "answers the all-zeros row; esolangs encode spells them",
    ),
)
