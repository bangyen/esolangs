"""Runtime and compiler capabilities for S*bleq."""

from esolangs.generation.wrap import wrap_grid
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "S*bleq",
    RuntimeSpec(
        "s_bleq",
        category="tape_based",
        eof="a failed read leaves the cell alone and the program runs on",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.s_bleq.generator", "s_bleq", ("truth_table",)
        ),
        wrap=wrap_grid,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
