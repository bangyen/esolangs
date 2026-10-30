"""Tests for the DINAC interpreter, pinned to the wiki's examples."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.dinac.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle

# Two lines carry a trailing space: ``OUT ' `` is the space of the greeting,
# ``OUT 'r `` has a stray one the parser must tolerate.
HELLO = (
    "OUT 'H\nOUT 'e\nOUT 'l\nOUT 'l\nOUT 'o\nOUT ',\nOUT ' \n"
    "OUT 'W\nOUT 'o\nOUT 'r \nOUT 'l\nOUT 'd\nOUT '!\nOUT \\n"
)
TRUTH = (
    "SET zeroOrOne:\\0\nIN zeroOrOne\nIF zeroOrOne = '1\n"
    "    WHILE 01\n        OUT '1\nELSE\n    OUT 00"
)
CAT = "SET c:\\0\nIN c\nWHILE c\n    IN c\n    OUT c"
CAT_REPAIRED = "SET c:\\0\nIN c\nWHILE c\n    OUT c\n    IN c"
PLUS_OR_MINUS = """\
DEF/\\0 aschar n:00
    SET res:\\0
    WHILE n ! 00
        res . res+
        n . n-
    GIVE res
SET c:\\0
SET acc:00
IN c
WHILE 01
    IF c = '+
        acc . acc+
        IN c
    ELSE
        IF c = '-
            OUT aschar(acc)
            acc . acc-
            IN c
        ELSE
            IN c"""
DEADFISH = """\
DEF/00 add a:00 b:00
    WHILE b
        a . a+
        b . b-
    GIVE a
DEF/00 and a:00 b:00
    IF a
        GIVE ~~b
    ELSE
        GIVE 00
DEF/00 greater a:00 b:00
    WHILE and(a,b)
        a . a-
        b . b-
    GIVE ~~a
DEF/00 mul a:00 b:00
    SET res:00
    WHILE b
        res . add(res,a)
        b . b-
    GIVE res
DEF/00 sub a:00 b:00
    WHILE b
        a . a-
        b . b-
    GIVE a
SET high:00
SET low:00
SET x:00
SET c:\\0
IN c
WHILE 01
    IF c = 'i
        IF low = FF
            low . 00
        ELSE
            low . low+
        IN c
    ELSE
        IF c = 'd
            IF low = 00
                IN c
            ELSE
                low . low-
                IN c
        ELSE
            IF c = 's
                x . mul(low,low)
                IF ~greater(low,0F)
                    low . x
                ELSE
                    high . sub(low,x)
                    low . x
                IF and(high = 01, low = 00)
                    high . 00
                    IN c
                ELSE
                    IN c
            ELSE
                IF c = 'o
                    OUT high
                    OUT low
                    IN c
                ELSE
                    IN c"""
# The page indents the bodies of add and mul one space short.
DEADFISH_RAW = DEADFISH.replace(
    "\n    WHILE b\n        a . a+\n        b . b-\n    GIVE a",
    "\n   WHILE b\n       a . a+\n       b . b-\n   GIVE a",
).replace(
    "\n    SET res:00\n    WHILE b\n        res . add(res,a)"
    "\n        b . b-\n    GIVE res",
    "\n   SET res:00\n   WHILE b\n       res . add(res,a)\n       b . b-\n   GIVE res",
)
AND = "DEF/00 and a:00 b:00\n    IF a\n        GIVE ~~b\n    ELSE\n        GIVE 00\n"


def out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_hello_world() -> None:
    assert out(HELLO) == "Hello, World!\n"


def test_truth_machine_prints_the_two_hex_digits() -> None:
    assert out(TRUTH, "0") == "00"


def test_truth_machine_one_loops_forever() -> None:
    io = ScriptedIO("1")
    assert run_until_halt_or_cycle(_Machine(TRUTH, io)) is False
    assert set(io.getvalue()) == {"1"}


def test_cat_as_written_drops_its_first_character_and_ends_on_nul() -> None:
    assert out(CAT, "Hi!") == "i!\0"


def test_repaired_cat_echoes_its_input() -> None:
    assert out(CAT_REPAIRED, "Hi!\nok") == "Hi!\nok"


def test_plus_or_minus_one_character_at_a_time() -> None:
    io = ScriptedIO("++-")
    assert run_until_halt_or_cycle(_Machine(PLUS_OR_MINUS, io)) is False
    assert io.getvalue() == "\x02"


def test_deadfish_as_written_breaks_the_four_space_rule() -> None:
    with pytest.raises(ValueError, match="indent of 3 spaces"):
        run(DEADFISH_RAW, ScriptedIO())


def test_deadfish_with_four_space_indents_runs() -> None:
    assert DEADFISH_RAW != DEADFISH
    io = ScriptedIO("iiso")
    run_until_halt_or_cycle(_Machine(DEADFISH, io))
    assert io.getvalue() == "0004"


def test_add1_with_a_one_digit_literal_is_refused_and_both_repairs_run() -> None:
    both = "DEF/00 add1 n:00\n    GIVE n+\nDEF/\\0 add1 n:\\0\n    GIVE n+\n"
    with pytest.raises(ValueError, match="malformed value '1'"):
        run(both + "OUT add1(1)", ScriptedIO())
    assert out(both + "OUT add1(01)") == "02"
    assert out(both + "OUT add1('1)") == "2"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("OUT \\n", "\n"),
        ("OUT '\\n", "\n"),
        ("OUT '#", "#"),
        ("OUT '(", "("),
        ("OUT FF", "FF"),
        ("OUT FF+", "00"),
        ("OUT 00-", "FF"),
        ("OUT \\0-", chr(127)),
        ("OUT 'a # note\nOUT 'b", "ab"),
        ("OUT $", "$"),
        ("OUT 01 = 01", "01"),
        ("OUT 01 ! 01", "00"),
        ("OUT 41 = 'A", "00"),
        ("OUT ~~05", "01"),
        ("OUT ~(01 = 01)", "00"),
        ("", ""),
    ],
)
def test_expressions(code: str, expected: str) -> None:
    assert out(code) == expected


def test_lowercase_hex_is_a_name() -> None:
    with pytest.raises(HaltError, match="undeclared name 'ff'"):
        run("OUT ff", ScriptedIO())


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        ("SET c:\\0\nIN c\nOUT c", "xyz", "x"),
        ("SET c:\\0\nIN c\nIN c\nOUT c", "ab", "b"),
        ("SET c:\\0\nIN c\nOUT c", "\n", "\n"),
        ("SET c:\\0\nIN c\nOUT c", "", "\0"),
        ("SET c:\\0\nIN c\nOUT c", "\u00e9", "\0"),
        ("SET n:00\nIN n\nOUT n", "255\n", "FF"),
        ("SET n:00\nIN n\nOUT n", "7", "07"),
        ("SET n:00\nIN n\nOUT n", "256\n", "00"),
        ("SET n:00\nIN n\nOUT n", "abc\n", "00"),
        ("SET n:00\nIN n\nOUT n", "\n", "00"),
        ("SET n:00\nIN n\nOUT n", "", "00"),
    ],
)
def test_input(code: str, stdin: str, expected: str) -> None:
    assert out(code, stdin) == expected


def test_functions_overload_recurse_and_loop() -> None:
    add = (
        "DEF/00 add a:00 b:00\n    WHILE b\n        a . a+\n"
        "        b . b-\n    GIVE a\n"
    )
    assert out(add + "OUT add(03,04)") == "07"
    assert out(AND + "OUT and(01,01)\nOUT and(01,00)") == "0100"
    assert out("DEF/$ shout\n    OUT 'h\n    OUT 'i\nshout()") == "hi"
    deep = (
        "DEF/00 d n:00\n    IF n\n        GIVE d(n-)\n"
        "    ELSE\n        GIVE 07\nOUT d(0A)"
    )
    assert out(deep) == "07"
    nested = AND + "OUT and(and(01,01),~and(01,00))"
    assert out(nested) == "01"


@pytest.mark.parametrize(
    ("code", "match"),
    [
        ("SET x:00\nx . 'a", "'x' is wubyte, cannot take a aschar"),
        ("SET x:$", "needs a typed initial value"),
        ("SET x:00\nSET x:01", "already declared"),
        ("x . 00", "undeclared name 'x'"),
        ("IN x", "no type to read into"),
        ("SET x:00\nIN x\nSET s:00\ns . $\nIN s", "no type to read into"),
        ("DEF/00 add n:00\n    GIVE n+\nOUT add(10,20)", "no overload of 'add'"),
        ("DEF/00 f n:00\n    GIVE 'a\nOUT f(01)", "'f' declares wubyte but gave"),
        (
            "DEF/00 f n:00\n    IF n\n        GIVE n\n"
            "    ELSE\n        OUT n\nOUT f(00)",
            "declares wubyte but gave snuval",
        ),
        ("GIVE 01", "GIVE outside a function"),
        ("OUT $+", "snuval"),
    ],
)
def test_runtime_errors(code: str, match: str) -> None:
    with pytest.raises(HaltError, match=match):
        run(code, ScriptedIO("1"))


@pytest.mark.parametrize(
    ("code", "match"),
    [
        ("IF 01\n    OUT 'a", "IF without its ELSE"),
        ("ELSE\n    OUT 'a", "ELSE without a matching IF"),
        ("WHILE 00\n   OUT 'a", "not a multiple of 4"),
        ("WHILE 00\nOUT 'a", "WHILE needs an indented body"),
        ("WHILE 00\n        OUT 'a", "indent jumps"),
        ("    OUT 'a", "unexpected indent"),
        ("DEF/$ f\n    DEF/$ g\n        OUT 'a", "may not be nested"),
        ("BLAH", "malformed statement"),
        ("OUT 'hi", "malformed value"),
        ("OUT (01", "unclosed parenthesis"),
        ("DEF/00 f n:00\n    OUT n", "never GIVEs"),
        ("DEF/$ f\n    OUT 'a\nDEF/$ f\n    OUT 'b", "duplicate overload"),
        ("DEF/$ f\n    OUT 'a\nSET f:00", "names both a function and a variable"),
        ("SET IF:00", "malformed SET"),
        ("OUT AND(01)", "not a function name"),
    ],
)
def test_malformed_programs(code: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        run(code, ScriptedIO())


def test_a_loop_inside_a_function_is_provably_endless() -> None:
    code = "DEF/00 spin n:00\n    WHILE 01\n        OUT n\n    GIVE n\nOUT spin(01)"
    assert run_until_halt_or_cycle(_Machine(code, ScriptedIO())) is False


def test_runaway_recursion_grows_frames_without_a_python_recursion_error() -> None:
    machine = _Machine("DEF/00 f n:00\n    GIVE f(n)\nOUT f(01)", ScriptedIO())
    for _ in range(4000):
        machine.step()
    assert len(machine.stack) > 1000
    assert not machine.halted


def test_debugger_views() -> None:
    machine = _Machine("SET x:05\nDEF/00 f n:00\n    GIVE n\nOUT f(x)", ScriptedIO())
    for _ in range(2):
        machine.step()
    assert machine.memory == [5]
    assert machine.stack == ["<top>", "f"]
    assert machine.ind == 0
