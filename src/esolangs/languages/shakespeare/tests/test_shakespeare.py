"""Tests for the Shakespeare interpreter."""

from itertools import product
from pathlib import Path

import pytest

from esolangs.exceptions import ExecutionTimeoutError, HaltError
from esolangs.languages.shakespeare._syntax import parse
from esolangs.languages.shakespeare.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import check_terminal
from tests.support.execution import run_observed as execute

FIXTURES = Path(__file__).parent / "fixtures"
HEAD = (
    "T.\nRomeo, a man.\nJuliet, a woman.\nHamlet, a prince.\nAct I: A.\nScene I: S.\n"
)
ON_STAGE = "[Enter Romeo and Juliet]\nRomeo:\n"


def _play(body: str, stage: str = ON_STAGE) -> str:
    return HEAD + stage + body + "\n"


def _run(body: str, stdin: str = "", stage: str = ON_STAGE) -> str:
    return execute("Shakespeare", _play(body, stage), stdin=stdin, timeout=10).output


def test_hello_world_prints_hello_world() -> None:
    """The page's Hello World; its output is unstated, so this is the intent."""
    source = (FIXTURES / "hello_world.spl").read_text()
    assert execute("Shakespeare", source, timeout=10).output == "Hello, World!\n"


def test_the_page_fragment_prints_minus_two_then_hamlet_plus_two() -> None:
    """Bounded signed powers, sum/product, stage and halt; Hamlet stays zero."""

    def noun(sign: int, adjectives: int) -> str:
        return "a " + "big " * adjectives + ("rose" if sign > 0 else "coward")

    for sa, sb, na, nb in product((-1, 1), (-1, 1), (*range(4), 32), range(4)):
        a, b = sa * 2**na, sb * 2**nb
        body = (
            f"You are {noun(sa, na)}!\n"
            f"Juliet:\nYou are {noun(sb, nb)}!\n"
            "You are the sum of Romeo and Juliet! Open your heart!\n"
            "Romeo:\nYou are the product of Romeo and Juliet! Open your heart!"
        )
        assert _run(body, "unused") == f"{a + b}{a * (a + b)}"
        state = ((a + b, a * (a + b), 0), (None,) * 3, (0, 1), False)
        check_terminal(
            _Machine,
            _play(body),
            "unused",
            lambda m: (m.state.values, m.state.stacks, m.state.stage, m.state.flag),
            (state, True, f"{a + b}{a * (a + b)}", 0, 0),
        )
    out = _run(
        "Thou art a vile coward! Open thy heart!\nJuliet:\n"
        "You are as lovely as the sum of Hamlet and a brave tree. Open thy heart."
    )
    assert out == "-22"


def test_truth_machine_halts_on_zero_and_repeats_one() -> None:
    source = (FIXTURES / "truth_machine.spl").read_text()
    assert execute("Shakespeare", source, stdin="0\n", timeout=10).output == "0"
    with pytest.raises(ExecutionTimeoutError) as info:
        execute("Shakespeare", source, stdin="1\n", max_steps=100)
    assert info.value.partial_output.startswith("1111")


def test_the_cats_repaired_spelling_runs_and_the_pages_typo_does_not() -> None:
    cat = (FIXTURES / "cat.spl").read_text()
    typo = (FIXTURES / "cat_wiki.spl").read_text()
    assert cat.replace("Open", "Ooen") == typo
    with pytest.raises(ValueError, match="ooen"):
        execute("Shakespeare", typo, stdin="x")


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        ("zero", 0),
        ("the sum of a big big rose and a rose", 5),
        ("the difference between a rose and a big big big rose", -7),
        ("the product of a big big rose and a bad coward", -8),
        ("the quotient between a bad big big big coward and a big rose", -8),
        ("the quotient between a bad big big big coward and a big big big rose", -2),
        (
            "the quotient between the difference between a bad coward and a rose"
            " and a big big rose",
            0,
        ),
        (
            "the remainder of the quotient between a bad big big big coward"
            " and a big big rose",
            0,
        ),
        (
            "the remainder of the quotient between the difference between"
            " a bad coward and a rose and a big big rose",
            -3,
        ),
        ("the square of a bad big coward", 16),
        ("the cube of a bad big coward", -64),
        ("the square root of a big big big big rose", 4),
        ("the square root of the sum of a big big big big rose and a rose", 4),
        ("the factorial of a big big big rose", 40320),
        ("twice twice a bad coward", -8),
        ("a stone wall", 1),
        ("the King", 1),
        ("a bad fat foul hairy hog", -16),
    ],
)
def test_values_and_operations(value: str, shown: int) -> None:
    assert _run(f"You are {value}! Open your heart!") == str(shown)


def test_a_missing_be_verb_and_the_other_second_person_words_parse() -> None:
    assert _run("You lying stupid big coward! Open your heart.") == "-8"
    assert _run("Thou art as big as a big rose. Open thine heart!") == "2"


def test_questions_guard_sentences_either_way() -> None:
    body = (
        "You are a big rose.\nJuliet:\nYou are a rose.\n"
        "Am I better than you? If so, Open your heart! If not, Speak your mind!"
    )
    assert _run(body) == "1"
    assert _run(body.replace("better", "worse")) == "\x01"
    assert _run(body.replace("better than", "as good as")) == "\x01"
    assert _run(body.replace("better", "more handsome")) == "1"
    assert _run(body.replace("better", "more foul")) == "\x01"


def test_a_goto_loops_within_its_act() -> None:
    source = (
        HEAD + ON_STAGE + "You are a big rose.\nScene II: L.\nRomeo:\n"
        "Open thy heart! You are the difference between yourself and a rose. "
        "Am I worse than you? If so, let us proceed to scene II.\n"
    )
    assert execute("Shakespeare", source, timeout=10).output == "21"


def test_stacks_remember_onto_the_listener_and_recall_into_it() -> None:
    out = _run(
        "You are a big rose. Remember a rose. Remember a big big rose. "
        "Recall my past. Open your heart. Recall my sins. Open your heart."
    )
    assert out == "41"
    from esolangs.languages.shakespeare.tests.oracle_checks import (
        check_workspace_shakespeare,
    )

    check_workspace_shakespeare()


def test_character_input_stores_the_code_and_number_input_a_token(monkeypatch) -> None:
    assert _run("Open your mind. Open your heart. Speak your mind.", "A") == "65A"
    assert _run("Listen to your heart. Open your heart.", "  -7 8") == "-7"
    from esolangs.languages.shakespeare import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Shakespeare",
        _play("Open your mind. Speak your mind."),
        interpreter,
        "_prepare_source",
        monkeypatch,
    )


def test_a_third_character_on_stage_halts() -> None:
    with pytest.raises(HaltError, match="two characters"):
        _run(
            "You are nothing.",
            stage="[Enter Romeo and Juliet]\n[Enter Hamlet]\nRomeo:\n",
        )


def test_a_character_off_stage_is_still_named_in_a_value() -> None:
    assert _run("You are the sum of Hamlet and a rose. Open your heart.") == "1"


def test_parse_counts_the_cast_and_the_operations() -> None:
    size, ops = parse(_play("You are a rose."))
    assert (size, len(ops)) == (3, 2)


def test_run_prints_through_the_io_it_is_given() -> None:
    io = ScriptedIO("")
    run(_play("You are a rose. Open your heart."), io)
    assert io.getvalue() == "1"
