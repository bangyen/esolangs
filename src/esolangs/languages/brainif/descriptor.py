"""Runtime and compiler capabilities for BrainIf."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "BrainIf",
    RuntimeSpec("brainif", category="tape_based", split=True),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.brainif.generator", "brainif", ("truth_table", "width")
        ),
        balance=FunctionRef(
            "esolangs.languages.brainif.generator", "_balance", ("_table", "default")
        ),
        no_wrap="each line is one instruction and goto targets are line numbers",
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
