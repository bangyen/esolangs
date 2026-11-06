"""Runtime and compiler capabilities for Interprogck8."""

from esolangs.languages.interprogck8.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

_MAX_INPUTS = 40


LANGUAGE = Language(
    "Interprogck8",
    RuntimeSpec(
        "interprogck8",
        completion_entrypoint="_execute_program",
        machine_preparation="prepare_machine",
        capabilities=CAPABILITIES,
        category="register_based",
        split=True,
        random=True,
    ),
    backend=BooleanBackend(
        restrictions=(
            f"at most {_MAX_INPUTS} inputs, past any table that fits in memory"
        ),
        entrypoint=FunctionRef(
            "esolangs.languages.interprogck8.generator",
            "interprogck8",
            ("truth_table",),
        ),
        no_wrap="a newline adds a line and moves every DownAccLines landing",
    ),
)
