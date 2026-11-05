"""Runtime and compiler capabilities for What!?."""

from esolangs.generation.wrap import TokenWrapper
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

_wrap = TokenWrapper(r'\[(?:\d+>|"[01]+":)|\d+|[?!]+|[\s\S]')


LANGUAGE = Language(
    "What!?",
    RuntimeSpec("what", category="tape_based", eof="a read at EOF yields 0"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.what.generator", "what", ("truth_table",)
        ),
        # Whitespace only separates tokens, so a newline between two is harmless.
        wrap=_wrap,
    ),
)
