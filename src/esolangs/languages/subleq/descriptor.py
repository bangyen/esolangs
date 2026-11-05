"""Runtime and compiler capabilities for Subleq."""

from esolangs.generation.wrap import wrap_grid
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Subleq",
    RuntimeSpec("subleq", category="tape_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.subleq.generator", "subleq", ("truth_table",)
        ),
        # Shared tree or packed lookup.
        shape=Shape.LOOKUP,
        wrap=wrap_grid,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
