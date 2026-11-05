"""Runtime and compiler capabilities for Streetcode."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Streetcode",
    RuntimeSpec(
        "streetcode",
        completion_entrypoint="_execute_program",
        category="grid_based",
        split=True,
        empty_program="Streetcode program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.streetcode.generator",
            "streetcode",
            ("truth_table", "width"),
        ),
        balance=FunctionRef(
            "esolangs.languages.streetcode.generator", "_balance", ("table", "default")
        ),
        grid=True,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
