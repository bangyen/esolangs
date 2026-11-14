"""Runtime and compiler capabilities for Sonata."""

from esolangs.languages.sonata.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.sonata.generator", "sonata_request"
        ),
        layout_width=False,
        # Not a tree: the table is a literal the row index strips.
        shape=Shape.LOOKUP,
        no_wrap="a newline ends a rule, and a rule cannot span two lines",
    )


LANGUAGE = LanguageDeclaration(
    "Sonata",
    RuntimeSpec(
        "sonata",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="program_based",
        eof="the input is the initial string, so an empty input is the empty string",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
        answer_mode="dump",
        answer_pattern="=([01])",
        note="Sonata's input is its initial string and its output the final "
        "one, = and the answer",
    ),
    example=Example(expected="=0"),
)
