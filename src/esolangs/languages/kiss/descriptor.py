"""Runtime and compiler capabilities for Kiss."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Kiss",
    RuntimeSpec(
        "kiss",
        category="other",
        empty_program="a Kiss program needs at least one combinator",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.kiss.generator", "kiss", ("truth_table",)
        ),
        wrap=wrap_chars,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
