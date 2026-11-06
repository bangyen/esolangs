"""Runtime and compiler capabilities for BASICER."""

from esolangs.languages.basicer.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "BASICER",
    RuntimeSpec(
        "basicer",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="program_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.basicer.generator", "basicer", ("truth_table",)
        ),
        no_wrap="each line is one instruction and a break splits it",
    ),
    contract=BooleanContract(alphabet=("1", "2")),
    example=Example(expected="0\n"),
)
