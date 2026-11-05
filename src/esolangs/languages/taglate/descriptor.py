"""Runtime and compiler capabilities for Taglate."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Taglate",
    RuntimeSpec("taglate", category="queue_based", split=True),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.taglate.generator", "taglate", ("truth_table", "width")
        ),
        # Both concatenate before tokenizing (Taglate after the queue seed; A
        # Painter Ant drops whitespace), so no break can land inside a command.
        wrap=FunctionRef(
            "esolangs.languages.taglate.wrapping", "_taglate", ("program", "width")
        ),
        wrap_multiline=True,
        same_layout=FunctionRef(
            "esolangs.languages.taglate.wrapping",
            "same_layout",
            ("template", "plain", "_layout"),
        ),
        balance=FunctionRef(
            "esolangs.languages.taglate.generator",
            "balance_taglate",
            ("_table", "default"),
        ),
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
