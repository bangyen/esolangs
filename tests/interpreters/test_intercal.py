"""C-INTERCAL expression, I/O, and NEXT-stack semantics."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.intercal import _expression, _Machine, run


def _run(source: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(source, io)
    return io.getvalue()


def test_vm_views_are_copies() -> None:
    machine = _Machine("PLEASE .1 <- #1\nDO GIVE UP\nDO GIVE UP", ScriptedIO(""))
    machine.step()
    memory = machine.memory
    memory.append(9)
    assert machine.memory == [1]


@pytest.mark.parametrize(
    "expression",
    ["", "'#1", "#65536"],
)
def test_invalid_expressions_raise(expression: str) -> None:
    with pytest.raises(HaltError):
        _expression(expression, {})


@pytest.mark.parametrize(
    ("statement", "stdin"),
    [
        (".1 <- #1#1", ""),
        ("READ OUT #1#1", ""),
        ("WRITE IN .1", "\n"),
        ("WRITE IN .1", "TEN\n"),
        ("RESUME #0", ""),
        ("FORGET #1#1", ""),
        ("IGNORE .1", ""),
    ],
)
def test_invalid_statements_raise(statement: str, stdin: str) -> None:
    source = f"PLEASE {statement}\nDO GIVE UP\nDO GIVE UP"
    with pytest.raises(HaltError):
        _run(source, stdin)


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


@pytest.mark.parametrize(
    "statement",
    [
        "RE\nAD OUT #1",
        "READ OUT #1\n2",
        ".1 <- #1\n2",
        ".1 <- #\n1",
        ".1 <\n- #1",
    ],
)
def test_newlines_cannot_split_keyword_number_or_operator(statement: str) -> None:
    with pytest.raises(HaltError):
        _run(f"PLEASE {statement}\nDO GIVE UP\nDO GIVE UP")


def test_truncated_group_after_whitespace_is_rejected() -> None:
    with pytest.raises(HaltError, match="incomplete INTERCAL expression"):
        _expression("'\n ", {})
