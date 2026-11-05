"""Runtime and compiler capabilities for thisthat."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "thisthat",
    RuntimeSpec(
        "thisthat",
        category="grid_based",
        random=True,
        split=True,
        eof="an exhausted '◇' sends the spec's empty transfer",
        empty_program="thisthat needs at least one start node",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.thisthat.generator",
            "thisthat",
            ("truth_table", "width"),
        ),
        balance=FunctionRef(
            "esolangs.languages.thisthat.generator",
            "_balance",
            ("truth_table", "default"),
        ),
        no_wrap="the H-tree's nodes and wires occupy fixed grid coordinates",
        grid=True,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
        ignores_whitespace=True,
        input_sets=True,
    ),
)
