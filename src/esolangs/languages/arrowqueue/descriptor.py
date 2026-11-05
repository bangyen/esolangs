"""Runtime and compiler capabilities for ArrowQueue."""

from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

PAIR = (".", "~")


LANGUAGE = Language(
    "ArrowQueue",
    RuntimeSpec("arrowqueue", category="grid_based", split=True),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.arrowqueue.generator",
            "arrowqueue",
            ("truth_table", "width"),
        ),
        balance=FunctionRef(
            "esolangs.languages.arrowqueue.generator", "_balance", ("table", "default")
        ),
        no_wrap="the queue and decision tree occupy fixed grid coordinates",
        template=TemplateSpec(pair=PAIR),
        grid=True,
    ),
    contract=BooleanContract(
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="ArrowQueue answers by termination -- it halts for a 0 result "
        "and loops forever for a 1, so only the halting branch is "
        "committed.  The headings printed are its interpreter-only "
        "queue dump, which the verdict does not read: the answer is "
        "that the program halted at all",
    ),
    example=Example(expected=""),
)
