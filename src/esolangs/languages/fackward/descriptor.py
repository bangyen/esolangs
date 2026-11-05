"""Runtime and compiler capabilities for Fackward."""

from esolangs.generation.wrap import TokenWrapper
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

_wrap = TokenWrapper(r"\d+|[\s\S]")


LANGUAGE = Language(
    "Fackward",
    RuntimeSpec("fackward", category="stack_based", eof="a read at EOF halts the run"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.fackward.generator", "fackward", ("truth_table",)
        ),
        # Whitespace only separates tokens, so a newline between two is harmless.
        wrap=_wrap,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
