"""Runtime and compiler capabilities for Home Row."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.home_row.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

HOME_ROW_PAIR = ("s", "j")


LANGUAGE = Language(
    "Home Row",
    RuntimeSpec(
        "home_row",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.home_row.generator", "home_row_request"
        ),
        layout_width=False,
        # A sum, not a tree: a lookup over the essential inputs only.
        shape=Shape.REDUCING,
        wrap=wrap_chars,
        template=TemplateSpec(pair=HOME_ROW_PAIR),
    ),
    contract=BooleanContract(),
)
