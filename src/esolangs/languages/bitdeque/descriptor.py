"""Runtime and compiler capabilities for Bitdeque."""

from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Bitdeque",
    RuntimeSpec("bitdeque", category="queue_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.bitdeque.generator",
            "bitdeque",
            ("truth_table", "width"),
        ),
        same_layout=FunctionRef(
            "esolangs.languages.bitdeque.generator",
            "_same_layout",
            ("template", "plain", "layout"),
        ),
        # Space-delimited, but ``GOTO`` and its target must stay on one line.
        wrap=FunctionRef(
            "esolangs.languages.bitdeque.generator", "_bitdeque", ("program", "width")
        ),
        balance=FunctionRef(
            "esolangs.languages.bitdeque.generator", "_balance", ("_table", "default")
        ),
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.bitdeque.generator",
                "bitdeque_setters",
                ("template", "n"),
            )
        ),
    ),
    contract=BooleanContract(
        answer_mode="dump",
        note="Bitdeque has no output instruction and dumps its deque at "
        "halt; the generator leaves exactly one bit on it, so the "
        "whole dump is the answer and there is no position to name",
    ),
)
