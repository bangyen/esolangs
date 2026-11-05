"""Runtime and compiler capabilities for DINAC."""

from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "DINAC",
    RuntimeSpec(
        "dinac",
        category="other",
        eof="reading past the input yields \\0 / 00, the value the cat example needs",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.dinac.generator", "dinac", ("truth_table",)
        ),
        shape=Shape.LOOKUP,
        no_wrap="each line is one statement and indentation is the block structure",
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
