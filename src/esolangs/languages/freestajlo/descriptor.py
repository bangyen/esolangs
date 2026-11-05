"""Runtime and compiler capabilities for Freestajlo."""

from esolangs.generation.wrap import TokenWrapper
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

_UNIT = r'"[^"]*"|\'[\s\S]|\d+|[\s\S]'


LANGUAGE = Language(
    "Freestajlo",
    RuntimeSpec(
        "freestajlo",
        category="stack_based",
        eof="an exhausted ',' is the spec's -1, an exhausted ';' its 0",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.freestajlo.generator", "freestajlo", ("truth_table",)
        ),
        shape=Shape.LOOKUP,
        wrap=TokenWrapper(_UNIT),
        balance=FunctionRef(
            "esolangs.languages.freestajlo.generator", "_balance", ("table", "default")
        ),
    ),
)
