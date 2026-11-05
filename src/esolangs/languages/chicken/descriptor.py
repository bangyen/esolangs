"""Runtime and compiler capabilities for Chicken."""

from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Chicken",
    RuntimeSpec(
        "chicken",
        category="stack_based",
        eof="a short input is a shorter string; a missing bit is not 1, so reads 0",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.chicken.generator", "chicken", ("truth_table",)
        ),
        shape=Shape.LOOKUP,
        no_wrap="a line break is the instruction boundary and a blank line is a cell",
    ),
    contract=BooleanContract(
        input_shape="char_stream",
        note="Chicken's input is one string; input[i] is bit i",
    ),
)
