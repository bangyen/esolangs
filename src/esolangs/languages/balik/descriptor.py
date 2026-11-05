"""Runtime and compiler capabilities for Balik."""

from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Balik",
    RuntimeSpec("balik", category="grid_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.balik.generator", "balik", ("truth_table",)
        ),
        shape=Shape.TREE,
        no_wrap="a newline adds a grid row and moves every vertical path",
    ),
)
