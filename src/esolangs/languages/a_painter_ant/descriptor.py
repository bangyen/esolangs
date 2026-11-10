"""Runtime and compiler capabilities for A Painter Ant."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.a_painter_ant.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

PAIR = ("n", "N")


LANGUAGE = Language(
    "A Painter Ant",
    RuntimeSpec(
        "a_painter_ant",
        completion_entrypoint="_execute",
        category="grid_based",
        machine_preparation="prepare_machine",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.a_painter_ant.generator", "a_painter_ant_request"
        ),
        layout_width=False,
        # Not a tree: one corridor cell per row, walked by the inputs' weights.
        shape=Shape.LOOKUP,
        wrap=wrap_chars,
        template=TemplateSpec(pair=PAIR),
    ),
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
