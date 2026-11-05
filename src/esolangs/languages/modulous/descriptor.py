"""Runtime and compiler capabilities for Modulous."""

from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Modulous",
    RuntimeSpec("modulous", category="stack_based", random=True),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.modulous.generator",
            "modulous",
            ("truth_table", "width"),
        ),
        # Not a tree: pops a ``PSH STR`` table down to the indexed character.
        shape=Shape.LOOKUP,
        balance=FunctionRef(
            "esolangs.languages.modulous.generator", "_balance", ("table", "default")
        ),
    ),
)
