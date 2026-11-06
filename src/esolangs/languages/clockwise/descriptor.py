"""Runtime and compiler capabilities for Clockwise."""

from esolangs.languages.clockwise.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Clockwise",
    RuntimeSpec(
        "clockwise",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        split=True,
        empty_program="Clockwise program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.clockwise.generator",
            "clockwise",
            ("truth_table", "width"),
        ),
        # Not a tree: a countdown stops on the entry's own column.
        shape=Shape.LOOKUP,
        balance=FunctionRef(
            "esolangs.languages.clockwise.generator", "_balance", ("table", "default")
        ),
        no_wrap="a row is a ring row; the walk's turns sit at fixed cells",
        grid=True,
    ),
    contract=BooleanContract(
        input_shape="char_stream_cyclic",
        note="Clockwise reads all its input bits in one go, so they go "
        "on one line -- one character per bit, not a line per bit, and "
        "not seven bits packed into a character: that packing is real "
        "but is on the output side. A line per bit, or a packed one, "
        "is read as a different row and answered wrongly",
    ),
)
