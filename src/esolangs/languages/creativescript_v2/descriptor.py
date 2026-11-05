"""Runtime and compiler capabilities for CreativeScript v2."""

from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "CreativeScript v2",
    RuntimeSpec(
        "creativescript_v2",
        category="register_based",
        empty_program="a CreativeScript v2 program needs at least one command",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.creativescript_v2.generator",
            "creativescript_v2",
            ("truth_table",),
        ),
        no_wrap="a break changes the line a command ends on",
        # No jump: the table is data, indexed by arithmetic, not a tree.
        shape=Shape.LOOKUP,
    ),
    contract=BooleanContract(),
)
