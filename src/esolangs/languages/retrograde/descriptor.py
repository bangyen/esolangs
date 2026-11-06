"""Runtime and compiler capabilities for Retrograde."""

from esolangs.generation.wrap import wrap_chars
from esolangs.languages.retrograde.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("\\", "*")


LANGUAGE = Language(
    "Retrograde",
    RuntimeSpec(
        "retrograde",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.retrograde.generator", "retrograde", ("truth_table",)
        ),
        wrap=wrap_chars,
        template=TemplateSpec(pair=PAIR),
    ),
    contract=BooleanContract(
        answer_mode="dump",
        note="Inputs are ordered one-instruction setters; the final current "
        "tape bit is the whole answer dump.",
    ),
)
