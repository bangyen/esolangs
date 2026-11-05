"""Runtime and compiler capabilities for Container."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Container",
    RuntimeSpec(
        "container",
        category="variable_based",
        split=True,
        # Wiki: the empty container sets IN "with EOF returning 0".
        eof="an exhausted read sets IN to the spec's 0",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.container.generator",
            "container",
            ("truth_table", "width"),
        ),
        balance=FunctionRef(
            "esolangs.languages.container.generator",
            "balance_container",
            ("table", "default"),
        ),
        no_wrap="each line declares a container or one of its rules",
    ),
    contract=BooleanContract(
        note="Container prints the answer; module.run returns the EXIT code.",
        input_shape="char_stream",
    ),
)
