"""Runtime and compiler capabilities for Bleh."""

from esolangs.generation.wrap import TokenWrapper
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

_TOKEN = r'"[^"]*"|::|\w+|[\s\S]'


LANGUAGE = Language(
    "Bleh",
    RuntimeSpec(
        "bleh",
        category="other",
        eof="an exhausted io::next() is the empty bitstring",
        underfed_raises=True,
        empty_program="a Bleh program needs a main function",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.bleh.generator", "bleh", ("truth_table",)
        ),
        wrap=TokenWrapper(_TOKEN),
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
