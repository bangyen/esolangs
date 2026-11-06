"""Runtime and compiler capabilities for IEBEL."""

from esolangs.languages.iebel.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "IEBEL",
    RuntimeSpec(
        "iebel",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.iebel.generator", "iebel", ("truth_table",)
        ),
        no_wrap="each line is one instruction; a break splits its fields",
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
