"""Runtime and compiler capabilities for brainfuck."""

from esolangs.generation.wrap import wrap_chars
from esolangs.languages.brainfuck.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "brainfuck",
    RuntimeSpec(
        "brainfuck",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.brainfuck.generator", "brainfuck", ("truth_table",)
        ),
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
