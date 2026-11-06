"""Runtime and compiler capabilities for lol waht i cant edit talk pages."""

from esolangs.languages.lol_waht_i_cant_edit_talk_pages.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "lol waht i cant edit talk pages",
    RuntimeSpec(
        "lol_waht_i_cant_edit_talk_pages",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="variable_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.lol_waht_i_cant_edit_talk_pages.generator",
            "lol_waht_i_cant_edit_talk_pages",
            ("truth_table",),
        ),
        no_wrap="every statement is one line, so a break splits a command",
    ),
)
