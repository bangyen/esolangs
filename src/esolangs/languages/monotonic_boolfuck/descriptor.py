"""Runtime and compiler capabilities for Monotonic Boolfuck."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Monotonic Boolfuck",
    RuntimeSpec(
        "monotonic_boolfuck", category="tape_based", eof="EOF supplies zero bits"
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.monotonic_boolfuck.generator",
            "monotonic_boolfuck",
            ("truth_table",),
        ),
        wrap=wrap_chars,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
