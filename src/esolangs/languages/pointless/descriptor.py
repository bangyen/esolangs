"""Runtime and compiler capabilities for Pointless."""

from esolangs.generation.wrap import TokenWrapper
from esolangs.languages.pointless.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

_wrap = TokenWrapper(r'"[^"]*"|[\s\S]')


LANGUAGE = Language(
    "Pointless",
    RuntimeSpec(
        "pointless",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.pointless.generator", "pointless", ("truth_table",)
        ),
        # Whitespace is a comment, so a newline anywhere outside a name is harmless.
        wrap=_wrap,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
