"""Runtime and compiler capabilities for Fargo."""

from esolangs.languages.fargo.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Fargo",
    RuntimeSpec(
        "fargo",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="the interpreter reads before the program starts",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.fargo.generator", "fargo", ("truth_table", "width")
        ),
        balance=FunctionRef(
            "esolangs.languages.fargo.generator", "_balance", ("table", "default")
        ),
        no_wrap="each physical line is one command; expressions have no continuation",
    ),
    contract=BooleanContract(
        input_shape="row_index",
        note="Fargo reads one number whose bits are the inputs, so the "
        "committed input is the row index rather than a bit per line",
    ),
)
