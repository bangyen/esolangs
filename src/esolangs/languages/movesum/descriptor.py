"""Runtime and compiler capabilities for Movesum."""

from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Movesum",
    RuntimeSpec(
        "movesum",
        category="tape_based",
        eof="a read at EOF is 0",
        empty_program="Movesum program is empty",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.movesum.generator", "movesum", ("truth_table",)
        ),
        # Not a tree: one rung per row, whatever the table says.
        shape=Shape.LOOKUP,
        no_wrap="each line is one instruction and a break splits it",
    ),
    example=Example(expected="0 0"),
)
