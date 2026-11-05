"""Runtime and compiler capabilities for EGL."""

from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "EGL",
    RuntimeSpec(
        "egl",
        category="grid_based",
        empty_program="EGL program must begin with 'width,height:'",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.egl.generator", "egl", ("truth_table", "width")
        ),
        # Not a tree: one painted grid cell per entry, walked to by weighted guards.
        shape=Shape.LOOKUP,
        balance=FunctionRef(
            "esolangs.languages.egl.generator", "_balance", ("_table", "default")
        ),
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
