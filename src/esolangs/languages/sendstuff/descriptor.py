"""Runtime and compiler capabilities for SendStuff."""

from esolangs.generation.wrap import TokenWrapper
from esolangs.languages.sendstuff.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

_wrap = TokenWrapper(r"[|<>!@]?[A-Za-z0-9_.%]+|[\s\S]")


LANGUAGE = Language(
    "SendStuff",
    RuntimeSpec(
        "sendstuff",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="an exhausted Input or InputNumber sends nothing, as the spec says",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.sendstuff.generator", "sendstuff", ("truth_table",)
        ),
        wrap=_wrap,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
