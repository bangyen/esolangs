"""C-INTERCAL expression, I/O, and NEXT-stack semantics."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.intercal import _expression, _Machine, run


def _run(source: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(source, io)
    return io.getvalue()


def test_calculate_mingle_select_unary_and_output() -> None:
    source = 'PLEASE .1 <- \'"&#1$#1"~"#65535$#0"\'\nDO READ OUT .1\nDO GIVE UP'
    assert _run(source) == "I\n"


def test_written_number_words_are_read() -> None:
    source = "PLEASE WRITE IN .1\nDO READ OUT .1\nDO GIVE UP"
    assert _run(source, "FOUR TWO\n") == "XLII\n"


def test_next_and_resume_return() -> None:
    source = "\n".join(
        [
            "PLEASE DO (10) NEXT",
            "DO READ OUT #1",
            "DO GIVE UP",
            "(10) DO RESUME #1",
        ]
    )
    assert _run(source) == "I\n"


def test_vm_views_are_copies() -> None:
    machine = _Machine("PLEASE .1 <- #1\nDO GIVE UP\nDO GIVE UP", ScriptedIO(""))
    machine.step()
    memory = machine.memory
    memory.append(9)
    assert machine.memory == [1]


@pytest.mark.parametrize(
    "expression",
    ["", "'#1", "\"'#1$#1'$#1\""],
)
def test_invalid_expressions_raise(expression: str) -> None:
    with pytest.raises(HaltError):
        _expression(expression, {})


def test_inactive_statement_is_skipped() -> None:
    source = "PLEASE .1 <- #0\nDON'T .1 <- #1\nDO READ OUT .1"
    assert _run(source) == "\n"


@pytest.mark.parametrize(
    ("statement", "stdin"),
    [
        (".1 <- #1#1", ""),
        ("READ OUT #1#1", ""),
        ("WRITE IN .1", "\n"),
        ("WRITE IN .1", "TEN\n"),
        ("FORGET #0", ""),
        ("FORGET #1#1", ""),
        ("IGNORE .1", ""),
    ],
)
def test_invalid_statements_raise(statement: str, stdin: str) -> None:
    source = f"PLEASE {statement}\nDO GIVE UP\nDO GIVE UP"
    with pytest.raises(HaltError):
        _run(source, stdin)


def test_forget_discards_next_frames_without_resuming() -> None:
    source = "\n".join(
        [
            "PLEASE DO (10) NEXT",
            "DO READ OUT #1",
            "DO GIVE UP",
            "(10) DO FORGET #1",
            "DO READ OUT #0",
        ]
    )
    assert _run(source) == "\n"


@pytest.mark.parametrize(
    "source",
    [
        "DO GIVE UP",
        "PLEASE GIVE UP\nPLEASE GIVE UP",
        "PLEASE RESUME #1\nDO GIVE UP\nDO GIVE UP",
    ],
)
def test_politeness_and_stack_errors(source: str) -> None:
    with pytest.raises(HaltError):
        _run(source)
