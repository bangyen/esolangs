"""Runtime and compiler capabilities for Malbolge."""

from esolangs.generation.wrap import wrap_chars
from esolangs.languages.malbolge.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

_DIGITS_N = 16
MAX_INPUTS = _DIGITS_N


LANGUAGE = Language(
    "Malbolge",
    RuntimeSpec(
        "malbolge",
        category="program_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        eof="an exhausted read is the value 59048, not an error",
    ),
    backend=BooleanBackend(
        max_inputs=MAX_INPUTS + 1,
        restrictions=(
            "seventeen inputs only for a table that ignores an input "
            "or is constant on Hamming-weight classes"
        ),
        entrypoint=FunctionRef(
            "esolangs.languages.malbolge.generator", "malbolge", ("truth_table",)
        ),
        # Not a tree: straight-line code into the fixed store.
        shape=Shape.LOOKUP,
        # Loader whitespace is discarded before assigning memory addresses.
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        note="the answer is one character and is printed with no newline",
        input_shape="char_stream",
    ),
)
