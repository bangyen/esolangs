"""Runtime and compiler capabilities for Nandypants."""

from esolangs.languages.nandypants.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Nandypants",
    RuntimeSpec(
        "nandypants",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.nandypants.generator", "nandypants", ("truth_table",)
        ),
        no_wrap="a line break inside a label would split one number into two",
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
