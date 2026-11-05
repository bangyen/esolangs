"""Runtime and compiler capabilities for LaserFuck."""

from esolangs.languages.laserfuck.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "LaserFuck",
    RuntimeSpec(
        "laserfuck",
        category="grid_based",
        random=True,
        split=True,
        # Seed 2 draws heading 0 (up), matching this language's examples.
        reproducible_seed=2,
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.laserfuck.generator",
            "laserfuck",
            ("truth_table", "width"),
        ),
        balance=FunctionRef(
            "esolangs.languages.laserfuck.generator",
            "balance_laserfuck",
            ("table", "default"),
        ),
        grid=True,
    ),
    contract=BooleanContract(
        answer_mode="dump",
        note="the initial heading is random by spec, so the example pins "
        "the source it is drawn from: seed 0 draws heading 3",
        input_shape="char_stream",
    ),
    example=Example(expected="0", kwargs=(("seed", 0),)),
)
