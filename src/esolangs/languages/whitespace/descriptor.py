"""Runtime and compiler capabilities for Whitespace."""

from esolangs.languages.whitespace.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec, SourceLoader

LANGUAGE = Language(
    "Whitespace",
    RuntimeSpec(
        "whitespace",
        source_loader=SourceLoader.VERBATIM,
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
        machine_preparation="prepare_machine",
        file_newline=False,
        empty_program="Whitespace program is empty",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.whitespace.generator", "whitespace", ("truth_table",)
        ),
        shape=Shape.REDUCING,
        no_wrap="a line feed is a token, so a break changes the command it splits",
    ),
)
