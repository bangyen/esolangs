"""Tests for the GridScript interpreter, against the page's sample programs."""

import re
import sys
from pathlib import Path

import pytest

from esolangs import Language
from esolangs.exceptions import HaltError, ProgramError
from esolangs.languages.gridscript.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO

_HEAD = "#T.\n@width 3\n@height 1\n(1,1):START\n"


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _prefix(code: str, steps: int, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for _ in range(steps):
        machine.step()
    return io.getvalue()


_TRUTH = (
    "#TRUTH MACHINE.\n@width 9\n@height 5\n(1,1):START\n(3,1):INPUT INT\n"
    "(5,1):GO EAST\n(7,1):SWITCH =1\n(7,3):PRINT 1\n(7,5):GO WEST\n"
    "(5,5):GO NORTH\n(9,1):PRINT 0\n"
)
_FACTORIAL = (
    "#FACTORIAL.\n@width 14\n@height 8\n(1,3):START\n(7,1):CHECKPOINT 0\n"
    "(3,3):INPUT INT TO n\n(5,3):STORE n\n(7,3):GO EAST\n(9,3):DECREMENT n\n"
    "(11,3):SWITCH n\n(11,5):MULTIPLY BY n\n(11,7):GOTO 0\n(13,3):PRINT\n"
)
_ACK = (
    "#ACKERMANN FUNCTION.\n@width 9\n@height 1\n(1,1):START\n(3,1):INPUT INT TO x\n"
    "(5,1):INPUT INT TO y\n(7,1):CALL ACK WITH ARGUMENTS x y\n(9,1):PRINT\n\n"
    "##ACK.\n@width 19\n@height 7\n(1,1):START\n(3,1):INPUT INT TO x\n"
    "(5,1):INPUT INT TO y\n(7,1):SWITCH !x\n(7,3):INCREMENT y\n(7,5):RETURN y\n"
    "(9,1):SWITCH !y\n(9,3):DECREMENT x\n(9,5):CALL ACK WITH ARGUMENTS x 1\n"
    "(9,7):RETURN\n(11,1):DECREMENT y\n(13,1):CALL ACK WITH ARGUMENTS x y GIVING z\n"
    "(15,1):DECREMENT x\n(17,1):CALL ACK WITH ARGUMENTS x z\n(19,1):RETURN\n"
)


def _east(*commands: str) -> str:
    body = "".join(f"({2 * i + 3},1):{cmd}\n" for i, cmd in enumerate(commands))
    return _HEAD.replace("@width 3", f"@width {2 * len(commands) + 1}") + body


def test_dynamic_variable_names_resolve_at_execution_time() -> None:
    source = _east(
        "INPUT STRING key",
        "STORE 17 TO THE VARIABLE NAMED key",
        "STORE 23 TO y",
        "INCREMENT THE VARIABLE NAMED key BY 2 GIVING THE VARIABLE NAMED 'result'",
        "PRINT result",
        "PRINT THE VARIABLE NAMED key",
    )
    assert _out(source, "x\n") == "1917"
    assert _out(source, "y\n") == "2523"
    with pytest.raises(HaltError, match="valid variable name"):
        _out(source, "not a name\n")


def test_nested_name_expressions_use_the_indirect_value() -> None:
    source = _east(
        "STORE 'which' TO alias",
        "STORE 'x' TO which",
        "STORE 17 TO x",
        "PRINT THE VARIABLE NAMED THE VARIABLE NAMED alias",
    )
    assert _out(source) == "17"


def test_input_passes_prompt_and_accepts_a_typed_dynamic_target() -> None:
    prompts: list[str] = []

    class PromptIO(ScriptedIO):
        def _read(self, prompt: str) -> str:
            prompts.append(prompt)
            return super()._read(prompt)

    source = _east(
        "STORE 'Number? ' TO message",
        "INPUT THE INT NAMED 'value' WITH PROMPT message",
        "PRINT value",
    )
    io = PromptIO("17\n")
    run(source, io)
    assert prompts == ["Number? "]
    assert io.getvalue() == "17"


def test_subroutine_input_does_not_evaluate_prompt() -> None:
    source = _east(
        "CALL F WITH ARGUMENTS 17 GIVING THE VARIABLE NAMED 'result'", "PRINT result"
    )
    function = _east(
        "INPUT INT x WITH PROMPT THE VARIABLE NAMED 'INVALID NAME'",
        "RETURN x",
    ).replace("#T.", "##F.", 1)
    assert _out(source + function) == "17"


@pytest.mark.parametrize("move", ["TO 7 1", "BY 4 0"])
def test_move_last_node_relocates_a_node_in_this_run(move: str) -> None:
    source = _east("PRINT 7", f"MOVE LAST NODE {move}", "PRINT 8")
    program = Language("GridScript").prepare(source)
    for _ in range(2):
        assert program.run().unwrap().output == "778"


def test_move_outside_the_program_removes_the_node() -> None:
    source = _east("PRINT 7", "MOVE LAST NODE TO 99 1", "GO WEST")
    assert _out(source) == "7"


def test_subroutine_calls_have_separate_program_spaces() -> None:
    main = _east("CALL F", "CALL F")
    body = _east("PRINT 7", "MOVE LAST NODE BY 4 0", "PRINT 8")
    assert _out(main + body.replace("#T.", "##F.", 1)) == "778778"


def test_goto_follows_a_relocated_checkpoint() -> None:
    source = _east(
        "CHECKPOINT 1", "MOVE LAST NODE TO 9 1", "GOTO 1", "PRINT 8", "PRINT 9"
    )
    assert _out(source) == "9"


def test_the_pages_sample_programs() -> None:
    assert _out(_HEAD.replace("START\n", "START\n(3,1):PRINT 'Hello World'\n")) == (
        "Hello World"
    )
    cat = (
        "#CAT PROGRAM.\n@width 11\n@height 1\n(1,1):START\n(3,1):CHECKPOINT 0\n"
        "(5,1):INPUT STRING s\n(7,1):SWITCH !s\n(9,1):PRINT s\n(11,1):GOTO 0\n"
    )
    # "halts when either 0 or the empty string is given"
    assert _out(cat, "ab\ncd\n0\nef\n") == "abcd"
    assert _out(cat, "ab\n\n") == "ab"
    assert _out(cat, "ab\r\r\n\n") == "ab\r"
    assert _out(_TRUTH, "0\n") == "0"
    assert _prefix(_TRUTH, 200, "1\n") == "1" * 12
    assert _out(_FACTORIAL, "5\n") == "120"
    assert [_out(_ACK, f"{x}\n{y}\n") for x, y in ((0, 0), (1, 2), (2, 3))] == [
        "1",
        "4",
        "9",
    ]
    fibonacci = (
        "#FIBONACCI SEQUENCE.\n@width 37\n@height 1\n@datawidth 10000\n"
        "@dataheight 1\n(1,1):START\n(3,1):STORE 1\n(5,1):NEXT VALUE\n"
        '(7,1):STORE 1\n(9,1):NEXT VALUE\n(11,1):PRINT "1 1"\n(13,1):CHECKPOINT 0\n'
        "(15,1):PREVIOUS VALUE\n(17,1):PREVIOUS VALUE\n(19,1):STORE TO a\n"
        "(21,1):NEXT VALUE\n(23,1):STORE TO b\n(25,1):INCREMENT a BY b GIVING c\n"
        '(27,1):PRINT " "\n(29,1):NEXT VALUE\n(31,1):STORE c\n(33,1):PRINT\n'
        "(35,1):NEXT VALUE\n(37,1):GOTO 0\n"
    )
    assert _prefix(fibonacci, 400).startswith("1 1 2 3 5 8 13 21 34 55 89 ")
    with pytest.raises(HaltError, match="32-bit"):  # fib(47) passes 2^31
        _out(fibonacci)


def test_a_node_holds_the_tracer_only_strictly_inside() -> None:
    # 99 Bottles turns north at x=6 under "<= radius" and re-enters the
    # DECREMENT column at x=7; strictly inside, it ends the song.
    wiki = Path(__file__).with_name("bottles.gs").read_text()
    song = _out(wiki)
    assert song.startswith(
        "99 bottles of beer on the wall,\n99 bottles of beer.\n"
        "Take one down and pass it around,\n99 bottles of beer on the wall!\n\n98"
    )
    assert song.endswith(
        "1 bottle of beer\nTake one down and pass it around,\n"
        "No more bottles of beer on the wall."
    )
    assert len(re.findall("Take one down", song)) == 100
    radius = "#R.\n@width 4\n@height 1\n@radius 2\n(1,1):START\n(3,1):PRINT 1\n"
    assert _out(radius) == "1"  # at x=2, distance 1 < 2


def test_values_casts_and_the_buffer() -> None:
    cases = [
        ("STORE 7\n(2,1):DIVIDE BY -2\n(2,1):PRINT", "-3"),  # truncates
        ("STORE 1.5 TO f\n(2,1):MULTIPLY f BY 2\n(2,1):PRINT f", "3.0"),
        ("STORE '12' TO s\n(2,1):INCREMENT s BY 1\n(2,1):PRINT s", "13"),
        (
            "SPLIT 'a 7 c'\n(2,1):REMOVE 1\n(2,1):PRINT\n(2,1):REMOVE TOP TO t\n"
            "(2,1):PRINT t\n(2,1):REMOVE TO u\n(2,1):PRINT u",
            "7ca",
        ),
        (
            "STORE 2\n(2,1):SPLIT 'x y z'\n"
            "(2,1):REMOVE THIS POSITION TO v\n(2,1):PRINT v",
            "z",
        ),
        ("REMOVE TO w\n(2,1):PRINT w\n(2,1):SWITCH w\n(2,1):PRINT TRUE", "TRUE"),
    ]
    for body, expected in cases:
        assert _out(_HEAD.replace("(1,1):START\n", f"(1,1):START\n(2,1):{body}\n")) == (
            expected
        ), body
    leave = "##F.\n(1,1):START\n(2,1):STORE 4\n"
    code = _HEAD + "(2,1):CALL F GIVING r\n(2,1):PRINT r\n(2,1):PRINT 5\n\n" + leave
    assert _out(code) == "5"  # leaving the space returns nothing: r is NULL


def test_decimal_operands_ignore_pythons_digit_limit() -> None:
    language = Language("GridScript")
    wide = "9" * 4301
    padded = "\N{ARABIC-INDIC DIGIT ZERO}" * 4301
    source = (
        _HEAD + f"@steps {wide}\n(2,1):CHECKPOINT {wide}\n"
        f"({padded}\N{ARABIC-INDIC DIGIT TWO},1):INPUT INT TO a\n(2,1):PRINT a\n"
        f"(2,1):PRINT +{padded}\N{ARABIC-INDIC DIGIT ONE}"
    )
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        for isolated in (False, True):
            assert (
                language.run(source, stdin=wide, isolated=isolated).unwrap().output
                == "1"
            )
            with pytest.raises(HaltError, match="overflows a 32-bit INT"):
                language.run(_HEAD + f"(2,1):PRINT {wide}", isolated=isolated).unwrap()
            with pytest.raises(ProgramError, match="a node lies outside"):
                language.run(_HEAD + f"({wide},1):PRINT 1", isolated=isolated).unwrap()
    finally:
        sys.set_int_max_str_digits(previous)


def test_fractional_tracer_positions_can_be_breakpoints() -> None:
    language = Language("GridScript")
    code = _HEAD.replace("@height 1", "@height 3") + "(2,1):GO 45"
    observer = language.make_debugger(code)
    for _ in range(3):
        observer.step()
    assert observer.ip == (0, 693, 256, 437, 256)

    debugger = language.make_debugger(code)
    debugger.break_at(observer.ip)
    assert debugger.run() == "breakpoint"
    assert debugger.ip == observer.ip


@pytest.mark.parametrize(
    ("body", "message", "output"),
    [
        (
            "(2,1):PRINT 'prefix'\n(2,1):DIVIDE BY 0\n(2,1):PRINT 'suffix'",
            "DIVIDE by zero",
            "prefix",
        ),
        ("@steps 1\n(2,1):GO EAST", "more than @steps 1 moves", ""),
    ],
)
def test_failed_steps_remain_pending(body: str, message: str, output: str) -> None:
    debugger = Language("GridScript").make_debugger(_HEAD + body)
    with pytest.raises(HaltError, match=message):
        debugger.run()
    snapshot = debugger.snapshot()
    for _ in range(2):
        with pytest.raises(HaltError, match=message):
            debugger.step()
        assert debugger.snapshot() == snapshot
        assert debugger.output == output


def test_errors() -> None:
    cases = [
        (_HEAD + "(2,1):GO RANDOM", ProgramError),  # never exercised
        ("#T.\n@width 3\n(1,1):START", ProgramError),  # no @height
        (_HEAD + "(2,1):RETURN", ProgramError),  # RETURN outside a subroutine
        (_HEAD + "(2,1):STORE 2147483647\n(2,1):INCREMENT", HaltError),
    ]
    for code, error in cases:
        with pytest.raises(error):
            _out(code)


def test_boolean_generator_bounds_its_index(monkeypatch: pytest.MonkeyPatch) -> None:
    from esolangs.languages.gridscript import generator

    monkeypatch.setattr(generator, "_INDEX_BITS", 1)
    monkeypatch.setattr(generator, "_CHUNK_INPUTS", 1)
    packed = generator.gridscript("0110")
    assert "REMOVE THIS POSITION" in packed
    assert "DIVIDE BY a" in packed
    assert _out(packed, "1\n1\n") == "0"

    # The leading input is ignored. The other three exceed the two-bit
    # packed route's reduced budget and select the tree.
    table = "01000101" * 2
    source = generator.gridscript(table)
    assert "REMOVE THIS POSITION" not in source
    assert "REMOVE TOP TO b" in source
    for row, answer in enumerate(table):
        port = ScriptedIO("\n".join(f"{row:04b}Q"))
        run(source, port)
        assert port.getvalue() == answer
        assert port.reads == 4
        assert port.input_str() == "Q"
