"""Runtime and compiler capabilities for Minsky Swap."""

from esolangs.languages.minsky_swap.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Minsky Swap",
    RuntimeSpec(
        "minsky_swap",
        category="register_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.minsky_swap.generator",
            "minsky_swap",
            ("truth_table", "width"),
        ),
        same_layout=FunctionRef(
            "esolangs.languages.minsky_swap.generator",
            "_same_layout",
            ("template", "plain", "layout"),
        ),
        # Each input adds its weight; a ``~`` cascade picks one of two leaves.
        shape=Shape.LOOKUP,
        balance=FunctionRef(
            "esolangs.languages.minsky_swap.generator", "_balance", ("table", "default")
        ),
        no_wrap="only line 1 is code; line 2 gives its numeric jump distances",
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.minsky_swap.generator",
                "minsky_swap_setters",
                ("template", "n"),
            )
        ),
    ),
    contract=BooleanContract(
        answer_mode="dump",
        note="Minsky Swap has no output instruction and dumps its "
        "registers at halt; the answer is the second one",
    ),
    example=Example(expected="1 0"),
)
