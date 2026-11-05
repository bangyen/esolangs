"""Runtime and compiler capabilities for Smallfuck."""

from esolangs.generation.wrap import wrap_chars
from esolangs.languages.smallfuck.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Smallfuck",
    RuntimeSpec(
        "smallfuck",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.smallfuck.generator",
            "smallfuck",
            ("truth_table", "width"),
        ),
        same_layout=FunctionRef(
            "esolangs.languages.smallfuck.generator",
            "_same_layout",
            ("template", "plain", "layout"),
        ),
        wrap=wrap_chars,
        balance=FunctionRef(
            "esolangs.languages.smallfuck.generator", "_balance", ("table", "default")
        ),
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.smallfuck.generator",
                "smallfuck_setters",
                ("template", "n"),
            )
        ),
    ),
    contract=BooleanContract(
        note="Smallfuck defines no I/O; this implementation prints final cell 2",
    ),
)
