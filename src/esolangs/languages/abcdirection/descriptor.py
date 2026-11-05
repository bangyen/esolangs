"""Runtime and compiler capabilities for ABCDirection."""

from esolangs.languages.abcdirection.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "ABCDirection",
    RuntimeSpec(
        "abcdirection",
        category="grid_based",
        eof="EOF supplies zero bits",
        empty_program="program must contain a line with DDDDDD",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.abcdirection.generator",
            "abcdirection",
            ("truth_table",),
        ),
        shape=Shape.REDUCING,
        balance=FunctionRef(
            "esolangs.languages.abcdirection.generator",
            "_balance",
            ("table", "default"),
        ),
        no_wrap="a newline adds a grid row and moves every vertical path",
        grid=True,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
