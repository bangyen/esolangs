"""C-INTERCAL expression, I/O, and NEXT-stack semantics."""

from functools import partial
from pathlib import Path

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.intercal import _expression, _Machine, run
from esolangs.interpreters.randomness import FirstDraw
from esolangs.vm import run_until_halt_or_all_branches_cycle
from tests.interpreters.runner import run_program

_run = partial(run_program, run, suppress_eof=False)


def test_calculate_mingle_select_unary_and_output() -> None:
    # The unary operator rotates right (manual s3.4.3, #&77 = 4): &3 keeps
    # bit0, not bit1.
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
    assert _run(source) == "_\n\n"


@pytest.mark.parametrize(
    ("statement", "stdin"),
    [
        (".1 <- #1#1", ""),
        ("READ OUT #1#1", ""),
        ("WRITE IN .1", "\n"),
        ("WRITE IN .1", "TEN\n"),
        ("RESUME #0", ""),
        ("FORGET #1#1", ""),
        # Manual s7.6: GIVE UP has no gerund.
        ("ABSTAIN FROM GIVING UP", ""),
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
    assert _run(source) == "_\n\n"


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


@pytest.mark.parametrize("statement", ["RE\nAD OUT #1", ".1 <\n- #1"])
def test_newlines_cannot_split_keyword_or_operator(statement: str) -> None:
    """C-INTERCAL's lexer matches READ{W}OUT and <- whole."""
    with pytest.raises(HaltError):
        _run(f"PLEASE {statement}\nDO GIVE UP\nDO GIVE UP")


@pytest.mark.parametrize(
    "statement", ["READ OUT #1\n2", ".1 <- #1\n2\nDO READ OUT .1", "READ OUT #\n1 2"]
)
def test_numbers_may_span_whitespace_as_in_the_c_lexer(statement: str) -> None:
    """lexer.l: a number is [0-9][ \\t\\n0-9]* and whitespace separates tokens."""
    assert _run(f"PLEASE {statement}\nDO GIVE UP\nDO GIVE UP") == "XII\n"


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
        ("READ OUT .0", "", "variable number"),
        ("(65536) DO GIVE UP", "", "label number"),
        ("WRITE IN .1x", "", "invalid INTERCAL variable"),
        ("READ OUT #65536", "", "out of range"),
        # E533: input above twospot range (4294967296).
        ("WRITE IN :1", "FOUR TWO NINE FOUR NINE SIX SEVEN TWO NINE SIX\n", "E533"),
        # Manual s7.3 and s7.6: these bodies parse as no statement (E000).
        (".1 <- ,1", "", "E000"),
        ("STASH #1", "", "E000"),
        ("WRITE IN .&1", "", "E000"),
        ("WRITE IN #1", "", "E000"),
        ("(1) GIVE UP", "", "E000"),
        ("ABSTAIN #1 (1)", "", "E000"),
        # E123: the NEXT stack is bounded.
        ("(1) NEXT\n(1) DO (1) NEXT", "", "stack overflow"),
    ],
)
def test_manual_limits_raise(statement: str, stdin: str, error: str) -> None:
    with pytest.raises(HaltError, match=error):
        _run(f"PLEASE {statement}\nDO GIVE UP\nDO GIVE UP", stdin)


def test_the_next_stack_holds_exactly_eighty_entries() -> None:
    """E123 fires on the 81st NEXT: every compiler's hard limit is 80 entries."""
    machine = _Machine("PLEASE (1) NEXT\n(1) DO (1) NEXT\nDO GIVE UP", ScriptedIO(""))

    def drive() -> None:
        while not machine.halted:
            machine.step()

    with pytest.raises(HaltError, match="stack overflow"):
        drive()
    assert len(machine.stack) == 80


def test_values_from_4000_print_an_overbar_line() -> None:
    """Manual s4.4.8: #4000 is IV with overbars; #3999 stays on one line."""
    assert _run("PLEASE READ OUT #4000\nDO READ OUT #3999\nDO GIVE UP") == (
        "__\nIV\nMMMCMXCIX\n"
    )


def test_roman_digits_five_to_eight_use_the_five_symbol() -> None:
    """Manual s4.4.8: 5-8 are V plus ones, 4 is IV, 9 is IX."""
    source = "PLEASE READ OUT #4\nDO READ OUT #6\nDO READ OUT #9\nDO READ OUT #38\n"
    source += "DO GIVE UP"
    assert _run(source) == "IV\nVI\nIX\nXXXVIII\n"


def _program(*statements: str, stdin: str = "", rng: FirstDraw | None = None) -> str:
    """Run one statement per line; the caller keeps the politeness ratio."""
    io = ScriptedIO(stdin)
    run("\n".join(statements), io, rng)
    return io.getvalue()


# Wikipedia's INTERCAL article: thirteen Turing Tape elements, no newline.
_HELLO = (
    "DO ,1 <- #13/PLEASE DO ,1 SUB #1 <- #238/DO ,1 SUB #2 <- #108/"
    "DO ,1 SUB #3 <- #112/DO ,1 SUB #4 <- #0/DO ,1 SUB #5 <- #64/"
    "DO ,1 SUB #6 <- #194/DO ,1 SUB #7 <- #48/PLEASE DO ,1 SUB #8 <- #22/"
    "DO ,1 SUB #9 <- #248/DO ,1 SUB #10 <- #168/DO ,1 SUB #11 <- #24/"
    "DO ,1 SUB #12 <- #16/DO ,1 SUB #13 <- #162/PLEASE READ OUT ,1/PLEASE GIVE UP"
)


def test_wikipedia_hello_world_uses_turing_tape_output() -> None:
    assert _program(*_HELLO.split("/")) == "Hello, world!"


def test_turing_tape_input_stores_differences_and_eof_as_256() -> None:
    """Manual s7.7.2: the code minus the previous code mod 256; EOF is 256."""
    out = _program(
        "PLEASE ,1 <- #3",
        "DO WRITE IN ,1",
        "DO READ OUT ,1 SUB #1 + ,1 SUB #2 + ,1 SUB #3",
        stdin="AB",
    )
    assert out == "LXV\nI\nCCLVI\n"


def test_manual_array_example_reads_nested_subscripts() -> None:
    """Manual s6.3.4's sample program: ;1 SUB #1 .1 ends up 1."""
    assert _program(
        "PLEASE ,1 <- #2",
        "DO .1 <- #2",
        "DO ,1 SUB .1 <- #1",
        "DO ,1 SUB #1 <- ,1 SUB #2",
        "PLEASE ;1 <- #2 BY #2",
        "DO ;1 SUB #1 #2 <- ,1 SUB ,1 SUB .1",
        "DO READ OUT ;1SUB#1.1",
        "DO READ OUT ;1 SUB #1 '#2~#3'",
        "DO GIVE UP",
    ) == ("I\nI\n")


@pytest.mark.parametrize(
    ("statement", "code"),
    [
        ("DO READ OUT ,1 SUB #3", "E241"),
        ("DO READ OUT ,1 SUB #1 #1", "E241"),
        ("DO WRITE IN ;2", "E241"),
        ("DO ,1 <- #0", "E240"),
    ],
)
def test_array_bounds_and_empty_dimensions_raise(statement: str, code: str) -> None:
    with pytest.raises(HaltError, match=code):
        _program("PLEASE ,1 <- #2", statement, "DO GIVE UP")


def test_mingle_builds_twospot_values() -> None:
    """Manual s6.3.1: 65536 is #0$#256, too big for a onespot (E275)."""
    assert _program("PLEASE :1 <- #0$#256", "DO READ OUT :1", "DO GIVE UP") == (
        "___      \nLXVDXXXVI\n"
    )
    with pytest.raises(HaltError, match="E275"):
        _program("PLEASE .1 <- #0$#256", "DO GIVE UP", "DO GIVE UP")


@pytest.mark.parametrize(
    ("twospot", "expected"),
    [("ONE THREE ONE ZERO SEVEN ONE", "XXI"), ("THREE ZERO", "X"), ("TWO ONE", "VII")],
)
def test_manual_select_examples(twospot: str, expected: str) -> None:
    """Manual s6.3.2: #21~:1 is 21, 10 or 7 for :1 = 1FFFF hex, 30 or 21.

    The manual's decimal "131061" contradicts its hex 1FFFF (131071).
    """
    out = _program(
        "PLEASE WRITE IN :1", "DO READ OUT #21~:1", "DO GIVE UP", stdin=twospot
    )
    assert out == expected + "\n"


def test_manual_unary_examples() -> None:
    """Manual s6.3.3: #V26 is 31 and #?26 is 23.

    Its "#&26 is 16" contradicts those two and C-INTERCAL's ick_and16
    (n & rotate-right(n)), which gives 8.
    """
    out = _program("PLEASE READ OUT #&26 + #V26 + ?#26", "DO GIVE UP", "DO GIVE UP")
    assert out == "VIII\nXXXI\nXXIII\n"


def test_stash_and_retrieve_restore_a_value() -> None:
    out = _program(
        "PLEASE .1 <- #1",
        "DO STASH .1",
        "DO .1 <- #2",
        "PLEASE RETRIEVE .1",
        "DO READ OUT .1",
        "DO GIVE UP",
    )
    assert out == "I\n"
    with pytest.raises(HaltError, match="E436"):
        _program("PLEASE RETRIEVE .1", "DO GIVE UP", "DO GIVE UP")


def test_ignore_makes_assignments_fail_silently_until_remember() -> None:
    out = _program(
        "PLEASE .1 <- #1",
        "DO IGNORE .1",
        "DO .1 <- #2",
        "DO READ OUT .1",
        "PLEASE REMEMBER .1",
        "DO .1 <- #3",
        "DO READ OUT .1",
        "DO GIVE UP",
    )
    assert out == "I\nIII\n"


def test_abstain_and_reinstate_by_gerund_and_label() -> None:
    """Manual s7.6: REINSTATE undoes DO NOT; GIVE UP cannot be reinstated."""
    out = _program(
        "PLEASE ABSTAIN FROM CALCULATING",
        "DO .1 <- #5",
        "DO REINSTATE (2)",
        "(1) DON'T GIVE UP",
        "PLEASE REINSTATE (1)",
        "(2) DO NOT READ OUT .1",
        "DO GIVE UP",
    )
    assert out == "_\n\n"


def test_come_from_takes_control_after_its_label_runs() -> None:
    out = _program(
        "(1) PLEASE READ OUT #1",
        "DO READ OUT #2",
        "DO COME FROM (1)",
        "DO READ OUT #3",
        "DO GIVE UP",
    )
    assert out == "I\nIII\n"


@pytest.mark.parametrize(("first", "expected"), [(0, "I\n"), (99, "")])
def test_double_oh_seven_draws_a_percentage(first: int, expected: str) -> None:
    """Manual s5.4: %50 runs when the draw below 100 is under 50."""
    out = _program(
        "PLEASE %50 READ OUT #1", "DO GIVE UP", "DO GIVE UP", rng=FirstDraw(first)
    )
    assert out == expected


def test_syntax_errors_raise_only_when_executed() -> None:
    """Manual s5.3: PLEASE NOTE is an abstained comment; DOUBT runs E000."""
    with pytest.raises(HaltError, match="E000"):
        _program("PLEASE NOTE THIS IS FINE", "DO READ OUT #1", "DOUBT THIS WILL WORK")


def test_millions_print_in_lowercase() -> None:
    """Manual s7.7.1: lowercase multiplies by a million; 4000000 is iv."""
    out = _program(
        "PLEASE WRITE IN :1",
        "DO READ OUT :1",
        "DO GIVE UP",
        stdin="FOUR ZERO ZERO ZERO ZERO ZERO ZERO",
    )
    assert out == "iv\n"


def test_write_in_an_array_element() -> None:
    out = _program(
        "PLEASE ,1 <- #2",
        "DO WRITE IN ,1 SUB #2",
        "DO READ OUT ,1 SUB #2",
        stdin="SEVEN",
    )
    assert out == "VII\n"


def test_once_and_again_self_abstain_and_self_reinstate() -> None:
    """Manual s5.5, over two passes of TRY AGAIN (s7.9)."""
    out = _program(
        "DO NOT READ OUT #1 ONCE",
        "PLEASE READ OUT #2 ONCE",
        "DO READ OUT #3 AGAIN",
        "DON'T READ OUT #4 AGAIN",
        "PLEASE DON'T GIVE UP ONCE",
        "DO TRY AGAIN",
    )
    assert out == "II\nIII\nI\nIII\n"


def test_computed_abstain_needs_as_many_reinstates() -> None:
    """Manual s7.6: ABSTAIN #2 double-abstains; one REINSTATE is not enough."""
    out = _program(
        "PLEASE ABSTAIN #2 FROM READING OUT",
        "DO REINSTATE READING OUT",
        "DO READ OUT #1",
        "DO GIVE UP",
    )
    assert out == ""


def test_retrieve_restores_an_array_but_not_an_ignored_scalar() -> None:
    """Manual s7.4: C-INTERCAL treats a retrieval like an assignment."""
    out = _program(
        "PLEASE ,1 <- #1",
        "DO ,1 SUB #1 <- #5",
        "DO .1 <- #7",
        "DO STASH ,1 + .1",
        "PLEASE .1 <- #8",
        "DO IGNORE .1",
        "DO ,1 <- #2",
        "PLEASE RETRIEVE ,1 + .1",
        "DO READ OUT ,1 SUB #1 + .1",
        "DO GIVE UP",
    )
    assert out == "V\nVIII\n"


@pytest.mark.parametrize(
    "source",
    [
        # NEXT FROM saves the place after (1); RESUME returns there.
        "(1) PLEASE READ OUT #1/DO GIVE UP/DO NEXT FROM (1)/DO READ OUT #3/"
        "DO RESUME #1",
        # Computed COME FROM: '#1$#0' is 2.
        "(2) PLEASE READ OUT #1/DO GIVE UP/DO COME FROM '#1$#0'/DO READ OUT #3/"
        "DO GIVE UP",
        # Gerund COME FROM; ONCE stops it firing a second time.
        "PLEASE READ OUT #1/DO GIVE UP/DO COME FROM READING OUT + WRITING IN ONCE/"
        "DO READ OUT #3/DO GIVE UP",
    ],
)
def test_next_from_computed_and_gerund_come_from(source: str) -> None:
    assert _program(*source.split("/")) == "I\nIII\n"


@pytest.mark.parametrize(
    ("source", "code"),
    [
        ("PLEASE COME FROM (9)/DO GIVE UP/DO GIVE UP", "E444"),
        ("(1) PLEASE GIVE UP/DO COME FROM (1)/DO COME FROM (1)", "E555"),
        ("PLEASE TRY AGAIN/DO GIVE UP/DO GIVE UP", "E993"),
        # Two computed COME FROMs fire together only at run time.
        ("(1) PLEASE .1 <- #1/DO COME FROM #1/DO COME FROM #1", "E555"),
    ],
)
def test_come_from_and_try_again_errors(source: str, code: str) -> None:
    with pytest.raises(HaltError, match=code):
        _program(*source.split("/"))


@pytest.mark.parametrize(("last", "halts"), [("GIVE UP", True), (".1 <- #2", False)])
def test_branch_search_explores_both_chance_outcomes(last: str, *, halts: bool) -> None:
    """A %30 statement that a COME FROM loops on halts only if it gives up."""
    source = f"PLEASE ,1 <- #1\nDO STASH ,1 + .1\nDO COME FROM (2)\n(2) DO %30 {last}"
    machine = _Machine(source, ScriptedIO(""))
    assert run_until_halt_or_all_branches_cycle(machine) is halts


def test_branch_search_cannot_fork_input() -> None:
    machine = _Machine("PLEASE WRITE IN .1\nDO GIVE UP\nDO GIVE UP", ScriptedIO(""))
    assert machine.branching_successors(machine.branching_snapshot(), 10) is None


def test_c_intercal_test2_multiplies_with_its_library_copy() -> None:
    """C-INTERCAL's pit/tests/test2.i (gitlab.com/esr/intercal, GPL-2.0+).

    Its library copy splits ``#`` from ``0`` across a line; test2.chk is XXXV.
    """
    path = Path(__file__).parents[1] / "fixtures" / "intercal_test2.i"
    assert _run(path.read_text(encoding="utf-8"), "FIVE\nSEVEN\n") == "XXXV\n"


@pytest.mark.parametrize(
    ("words", "out"), [("BAT BI", "XII\n"), ("NULI EKA", "I\n"), ('J\\"OL', "VIII\n")]
)
def test_digits_in_the_manuals_other_languages_are_read(words: str, out: str) -> None:
    # Basque, Georgian + Sanskrit, Volapuk (TeX spelling); C-INTERCAL's numerals.c.
    source = "PLEASE WRITE IN .1\nDO READ OUT .1\nDO GIVE UP"
    assert _run(source, words + "\n") == out


def test_a_label_after_the_coming_from_gerund_starts_a_statement() -> None:
    # Was one statement, ABSTAIN FROM COMING FROM (1), and E000.
    assert (
        _program("PLEASE ABSTAIN FROM COMING FROM", "(1) DO READ OUT #1", "DO GIVE UP")
        == "I\n"
    )


@pytest.mark.parametrize("target", ["(1)", "COMING FROM"])
def test_a_come_from_finishing_fires_what_comes_from_it(target: str) -> None:
    """The manual: DO COME FROM COMING FROM is an infinite loop; so is (1)'s."""
    source = f"(1) PLEASE COME FROM {target}\nDO GIVE UP\nDO GIVE UP"
    assert (
        run_until_halt_or_all_branches_cycle(_Machine(source, ScriptedIO(""))) is False
    )
