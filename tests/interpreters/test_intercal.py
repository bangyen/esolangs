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
    # Unary rotates right (manual s3.4.3, #&77 = 4): &3 keeps bit0, not bit1.
    source = 'PLEASE .1 <- \'"&#1$#1"~"#0$#65535"\'\nDO READ OUT .1\nDO GIVE UP'
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
    # E533 limits mingle by value (manual s9), so '#1$#1'$#1 is legal.
    ["", "'#1", "\"'#65535$#65535'$#1\""],
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
        ("RESUME #0", ""),
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


@pytest.mark.parametrize(
    "source",
    [
        # '?.2$#1' sets bit31 (right rotation), overflowing .1 (E275).
        "PLEASE\n.1\n<-\n'\n?\n#1\n$\n.2\n'\nDO\nREAD\nOUT\n.1\nDO\nGIVE\nUP",
        "PLEASE\nDO\n.1 <- '#0 $ #1' DO READ OUT .1 DO GIVE UP",
    ],
)
def test_logical_statements_allow_token_boundary_newlines(source: str) -> None:
    machine = _Machine(source, ScriptedIO(""))
    assert len(machine.lines) == 3
    expected = "III\n" if "?" in source else "I\n"
    assert _run(source) == expected


def test_wrapped_labels_next_resume_and_input() -> None:
    source = (
        "PLEASE\nDO\n(10)\nNEXT\nDO\nREAD\nOUT\n.1\nDO\nGIVE\nUP\n"
        "(10)\nDO\nWRITE\nIN\n.1\nDO\nRESUME\n#1"
    )
    assert _run(source, "ONE\n") == "I\n"


def test_bare_core_lines_remain_separate_statements() -> None:
    source = "PLEASE .1 <- #1\nREAD OUT .1\nGIVE UP"
    assert _run(source) == "I\n"


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


def test_empty_lines_do_not_count_toward_politeness() -> None:
    assert _run("\nPLEASE\n\nREAD OUT #1\n\nDO GIVE UP\nDO GIVE UP\n") == "I\n"


def test_truncated_group_after_whitespace_is_rejected() -> None:
    with pytest.raises(HaltError, match="incomplete INTERCAL expression"):
        _expression("'\n ", {})


def test_manual_unary_example_and_operand_placement() -> None:
    """Manual s3.4.3: ``#&77`` is 4; the unary sits after the mesh."""
    assert _run("PLEASE READ OUT #&77\nDO GIVE UP\nDO GIVE UP") == "IV\n"


def test_forget_zero_is_a_no_op() -> None:
    """Only RESUME #0 is an error (manual s4.4.4); FORGET #0 discards nothing."""
    assert _run("PLEASE FORGET #0\nDO READ OUT #1\nDO GIVE UP") == "I\n"


@pytest.mark.parametrize(
    ("statement", "stdin", "error"),
    [
        # E275: a 32-bit value assigned to a onespot is not masked.
        (".1 <- '#65535$#1'", "", "assignment overflow"),
        # Manual s4.4.7: 65536 into a 16-bit variable is DON'T BYTE OFF.
        ("WRITE IN .1", "SIX FIVE FIVE THREE SIX\n", "input overflow"),
        # E182: a label defined twice.
        ("GIVE UP\n(1) DO GIVE UP\n(1) DO GIVE UP", "", "duplicate"),
        # E129: a NEXT to a missing label.
        ("(2) NEXT", "", "unknown"),
        # Variables and constants run 1..65535 and 0..65535.
        (".0 <- #1", "", "variable number"),
        ("READ OUT #65536", "", "out of range"),
        # E123: the NEXT stack is bounded (79 per the manual, 80 in C-INTERCAL).
        ("(1) NEXT\n(1) DO (1) NEXT", "", "stack overflow"),
    ],
)
def test_manual_limits_raise(statement: str, stdin: str, error: str) -> None:
    with pytest.raises(HaltError, match=error):
        _run(f"PLEASE {statement}\nDO GIVE UP\nDO GIVE UP", stdin)


def test_values_from_4000_print_an_overbar_line() -> None:
    """Manual s4.4.8: #4000 is IV with overbars; #3999 stays on one line."""
    assert _run("PLEASE READ OUT #4000\nDO READ OUT #3999\nDO GIVE UP") == (
        "__\nIV\nMMMCMXCIX\n"
    )
