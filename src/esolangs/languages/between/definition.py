"""Between metadata, independent of its implementations."""

from esolangs.registry._backend import DeferredBackend, GeneratorReference
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Between",
    RuntimeSpec("between", category="register_based"),
    backend=DeferredBackend(
        generate=GeneratorReference("esolangs.languages.between.generator", "between"),
        no_wrap="each line is one instruction and a break splits it",
    ),
)
