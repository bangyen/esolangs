"""Runtime and compiler capabilities for Whitespace."""

from esolangs.generation.requests import GenerationRequest
from esolangs.languages.whitespace.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec, VerbatimSourcePolicy
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Whitespace",
    RuntimeSpec(
        "whitespace",
        source_policy=VerbatimSourcePolicy(),
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
        machine_preparation="prepare_machine",
        empty_program="Whitespace program is empty",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.whitespace.generator", "whitespace_request"
        ),
        layout_width=False,
        shape=Shape.REDUCING,
        no_wrap="a line feed is a token, so a break changes the command it splits",
    ),
)
