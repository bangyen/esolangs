"""Runtime and compiler capabilities for Blindfolded Arithmetic."""

from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Blindfolded Arithmetic",
    RuntimeSpec(
        "blindfolded_arithmetic",
        category="register_based",
        empty_program="a Blindfolded Arithmetic program needs at least one instruction",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.blindfolded_arithmetic.generator",
            "blindfolded_arithmetic",
            ("truth_table",),
        ),
        wrap=FunctionRef(
            "esolangs.languages.blindfolded_arithmetic.generator",
            "_wrap",
            ("program", "width"),
        ),
        # No flow control: the table is data, indexed by arithmetic, not a tree.
        shape=Shape.LOOKUP,
    ),
    contract=BooleanContract(
        input_shape="row_number",
        note="the input must be a positive integer, so the committed input is "
        "the row index plus one",
    ),
)
