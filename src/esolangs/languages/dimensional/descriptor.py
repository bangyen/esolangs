"""Runtime and compiler capabilities for Dimensional."""

from esolangs.generation.wrap import _dimensional
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Dimensional",
    RuntimeSpec("dimensional", category="tape_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.dimensional.generator",
            "dimensional",
            ("truth_table", "width"),
        ),
        # Not a tree: one painted cell per entry along dimension 1.
        shape=Shape.LOOKUP,
        wrap=_dimensional,
        balance=FunctionRef(
            "esolangs.languages.dimensional.generator", "_balance", ("table", "default")
        ),
    ),
)
