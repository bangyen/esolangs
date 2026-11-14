"""Runtime and compiler capabilities for A Painter Ant."""

from esolangs.languages.a_painter_ant.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("n", "N")


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, Shape, TemplateSpec
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.a_painter_ant.generator", "a_painter_ant_request"
        ),
        layout_width=False,
        # Not a tree: one corridor cell per row, walked by the inputs' weights.
        shape=Shape.LOOKUP,
        wrap=wrap_chars,
        template=TemplateSpec(pair=PAIR),
    )


LANGUAGE = LanguageDeclaration(
    "A Painter Ant",
    RuntimeSpec(
        "a_painter_ant",
        completion_entrypoint="_execute",
        category="grid_based",
        machine_preparation="prepare_machine",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"(?m)^[.#o@]*([o@])[.#o@]*$",
        answer_values=("o", "@"),
        note="A Painter Ant has no output: it paints a grid and the answer "
        "is the colour of the cell the ant rests on, "
        "shown by 'o' (on black, a zero) or '@' (on white, a one)",
    ),
    example=Example(expected="....\n####\n.o.#"),
)
