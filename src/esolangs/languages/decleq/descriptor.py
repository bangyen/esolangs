"""Runtime and compiler capabilities for Decleq."""

from esolangs.generation.wrap import wrap_grid
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Decleq",
    RuntimeSpec("decleq", category="register_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.decleq.generator", "decleq", ("truth_table",)
        ),
        wrap=wrap_grid,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
