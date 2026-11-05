"""Runtime and compiler capabilities for CV(N)(C)."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "CV(N)(C)",
    RuntimeSpec("cvnc", category="other", empty_program="program is empty"),
    # The parentheses mark optional slots; the language is written as one word.
    id="cvnc",
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.cvnc.generator", "cvnc", ("truth_table",)
        ),
        # LF-only source-format deviation: discard breaks before parsing or addressing.
        wrap=wrap_chars,
    ),
)
