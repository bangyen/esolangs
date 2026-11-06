"""Runtime and compiler capabilities for Crement."""

from esolangs.languages.crement.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Crement",
    RuntimeSpec(
        "crement",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="program_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.crement.generator", "crement", ("truth_table", "width")
        ),
        same_layout=FunctionRef(
            "esolangs.languages.crement.generator",
            "_same_layout",
            ("template", "plain", "layout"),
        ),
        balance=FunctionRef(
            "esolangs.languages.crement.generator", "_balance", ("_table", "default")
        ),
        no_wrap="jumps and patches name instruction numbers, so lines stay whole",
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.crement.generator",
                "crement_setters",
                ("template", "n"),
            )
        ),
    ),
    contract=BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="Crement answers by termination: the tree's nodes patch a "
        "per-input tester's jump targets, and the row lands past the "
        "end (halts, 0) or on a self-jump (diverges, 1)",
    ),
    example=Example(expected=""),
)
