"""Runtime and compiler capabilities for Sonata."""

from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Sonata",
    RuntimeSpec(
        "sonata",
        category="program_based",
        eof="the input is the initial string, so an empty input is the empty string",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.sonata.generator", "sonata", ("truth_table",)
        ),
        # Not a tree: the table is a literal the row index strips.
        shape=Shape.LOOKUP,
        no_wrap="a newline ends a rule, and a rule cannot span two lines",
    ),
    contract=BooleanContract(
        input_shape="char_stream",
        answer_mode="dump",
        answer_pattern="=([01])",
        note="Sonata's input is its initial string and its output the final "
        "one, = and the answer",
    ),
    example=Example(expected="=0"),
)
