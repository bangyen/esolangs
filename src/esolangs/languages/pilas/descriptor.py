"""Runtime and compiler capabilities for Pilas."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Pilas",
    RuntimeSpec("pilas", category="stack_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.pilas.generator", "pilas", ("truth_table",)
        ),
        no_wrap="a newline starts line two, which runs a different stack",
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
