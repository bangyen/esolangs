"""Runtime and compiler capabilities for Boolfuck."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Boolfuck",
    RuntimeSpec("boolfuck", category="tape_based", eof="EOF supplies zero bits"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.boolfuck.generator", "boolfuck", ("truth_table",)
        ),
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
