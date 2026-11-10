"""Runtime and compiler capabilities for CV(N)(C)."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.cvnc.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "CV(N)(C)",
    RuntimeSpec(
        "cvnc",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        empty_program="program is empty",
    ),
    # The parentheses mark optional slots; the language is written as one word.
    id="cvnc",
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.cvnc.generator", "cvnc_request"
        ),
        layout_width=False,
        # LF-only source-format deviation: discard breaks before parsing or addressing.
        wrap=wrap_chars,
    ),
)
