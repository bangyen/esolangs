"""Runtime and compiler capabilities for Qrain."""

from esolangs.generation.wrap import wrap_chars
from esolangs.languages.qrain.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Qrain",
    RuntimeSpec(
        "qrain",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="queue_based",
        eof="EOF supplies byte 0",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.qrain.generator", "qrain", ("truth_table",)
        ),
        wrap=wrap_chars,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
