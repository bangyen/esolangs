"""Tests for the Basicfuck interpreter."""

import pytest

from esolangs.exceptions import HaltError, ProgramError
from esolangs.languages.basicfuck.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.contract import CycleContract, EmptyProgramContract

#: Directive and allocation lines for a few variables, wrapping bytes.
WRAP = "#basicfuck t=unbounded r=0~255 o=wrap\n"
NEAREST = "#basicfuck t=unbounded r=0~ o=nearest\n"

#: The wiki's cat, apart from the directive and one comment's wording.
CAT = (
    WRAP
    + """#allocate char, eof255

read -> char;
while (char) {
    write <- char;
    char -= char;  // This line is to support EOF = no change.
    read -> char;

    // These support EOF = -1 = 255.
    eof255 -= eof255;  // First, we clear 'eof255'.
    eof255 += char;  // Then we increment 'eof255' by the value of 'char'.
    eof255 += 1;  // Finally, we add one so that a value of 255 wraps over to 0.

    if !(eof255) {
        char -= char;  // If eof255 is zero, set char to 0 to break out.
    }
}
"""
)


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _machine(code: str) -> _Machine:
    return _Machine(code, ScriptedIO(""))


def test_the_wiki_cat_copies_until_a_zero_byte() -> None:
    """EOF is unspecified (the cat covers three conventions), so a NUL ends it."""
    assert _run(CAT, "hi\x00") == "hi"


def test_the_wiki_cat_stops_on_255() -> None:
    assert _run(CAT, "abÿ") == "ab"


def test_the_wiki_cat_at_eof_raises() -> None:
    with pytest.raises(EOFError):
        _run(CAT, "ab")


def test_the_wiki_assignment_zeroes_then_adds() -> None:
    code = NEAREST + "#allocate v\nv += 21; v -= v; v += 3; write <- v;"
    assert _run(code) == "\x03"


def test_the_wiki_multiplication_leaves_the_product() -> None:
    code = (
        NEAREST
        + """#allocate x, y, y2, result
x += 8; y += 3; y2 += y;
while (y2) { result += x; y2 -= 1; }
write <- result;"""
    )
    assert _run(code) == "\x18"


def test_the_wiki_array_example_addresses_by_offset() -> None:
    """``arr->3`` is ``z``, the cell after the array's last."""
    code = (
        NEAREST
        + """#allocate a, b, x, y, arr->3, z
y += 23;
arr->2 += y;
arr->3 += 1;
write <- arr->2; write <- z;"""
    )
    assert _run(code) == "\x17\x01"


def test_array_and_variable_name_one_cell() -> None:
    code = WRAP + "#allocate a, arr->2\narr->1 += 65; write <- arr->1;"
    assert _run(code) == "A"


@pytest.mark.parametrize(
    ("mode", "result"),
    [("nearest", "\xff"), ("wrap", "\x2c")],
)
def test_overflow_rule(mode: str, result: str) -> None:
    code = f"#basicfuck t=1 r=0~255 o={mode}\n#allocate a\na += 300; write <- a;"
    assert _run(code) == result


def test_underflow_wraps_to_the_top_and_clamps_to_the_bottom() -> None:
    wrap = "#basicfuck t=1 r=0~255 o=wrap\n#allocate a\na -= 1; write <- a;"
    near = "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\na -= 1; write <- a;"
    assert (_run(wrap), _run(near)) == ("\xff", "\x00")


@pytest.mark.parametrize("body", ["a += 256;", "a -= 1;"])
def test_halt_mode_stops_on_overflow(body: str) -> None:
    with pytest.raises(HaltError):
        _run("#basicfuck t=1 r=0~255 o=halt\n#allocate a\n" + body)


def test_negative_minimum_is_a_range() -> None:
    code = "#basicfuck t=1 r=-2~2 o=nearest\n#allocate a\na -= 9; a += 3; write <- a;"
    assert _run(code) == "\x01"


def test_if_and_negated_if() -> None:
    code = WRAP + "#allocate a\nif (a) { write <- a; } if !(a) { a += 65; write <- a; }"
    assert _run(code) == "A"


def test_while_not_runs_until_nonzero() -> None:
    code = (
        WRAP + "#allocate a, n\nwhile !(a) { n += 1; if (n) { a += n; } }\nwrite <- n;"
    )
    assert _run(code) == "\x01"


def test_read_takes_characters_including_newlines() -> None:
    code = WRAP + "#allocate a\nread -> a; write <- a; read -> a; write <- a;"
    assert _run(code, "x\n") == "x\n"


def test_comments_and_blank_lines_are_ignored() -> None:
    code = "// c\n\n" + WRAP + "#allocate a // names\na += 66; // b\nwrite <- a;"
    assert _run(code) == "B"


def test_a_variable_operand_costs_a_spare_cell() -> None:
    body = "#allocate a, b\na += 1; b += a;"
    assert _run("#basicfuck t=3 r=0~255 o=wrap\n" + body) == ""
    with pytest.raises(ValueError, match="insufficient memory"):
        _run("#basicfuck t=2 r=0~255 o=wrap\n" + body)


def test_a_constant_operand_needs_no_spare_cell() -> None:
    assert _run("#basicfuck t=2 r=0~255 o=wrap\n#allocate a, b\na += 1; b += 2;") == ""


def test_an_index_outside_the_tape_halts() -> None:
    with pytest.raises(HaltError):
        _run(WRAP + "#allocate a->2\na->2 += 1;")


def test_an_unreached_bad_index_is_harmless() -> None:
    assert _run(WRAP + "#allocate a\nif (a) { a->5 += 1; }") == ""


def test_an_unwritable_value_halts() -> None:
    with pytest.raises(HaltError):
        _run("#basicfuck t=1 r=-5~5 o=nearest\n#allocate a\na -= 1; write <- a;")


@pytest.mark.parametrize(
    "code",
    [
        "",
        "#allocate a\n",
        "#basicfuck t=1 r=0~255 o=bad\n#allocate a\n",
        "#basicfuck t=1 r=0~255\n#allocate a\n",
        "#basicfuck t=1 r=0~ o=wrap\n#allocate a\n",
        "#basicfuck t=1 r=9~3 o=halt\n#allocate a\n",
        WRAP + "a += 1;",
        WRAP + "#allocate a b\n",
        WRAP + "#allocate write\n",
        WRAP + "#allocate a, a\n",
        WRAP + "#allocate a\nz += 1;",
        WRAP + "#allocate a\na += ;",
        WRAP + "#allocate a\na 5 1;",
        WRAP + "#allocate a\na += 1",
        WRAP + "#allocate a\nwrite a;",
        WRAP + "#allocate a\nread a;",
        WRAP + "#allocate a\nif (a { a += 1; }",
        WRAP + "#allocate a\nif (a) { write <- a;",
        WRAP + "#allocate a\nif (a) { } }",
        WRAP + "#allocate a\nif (a) { }; a += 1;",
        WRAP + "#allocate a\na += 1 @ 2;",
        WRAP + "#allocate a, i\na->i += 1;",
        "#basicfuck t=0 r=0~255 o=wrap\n#allocate a\n",
    ],
)
def test_malformed_programs_raise_value_error(code: str) -> None:
    with pytest.raises(ProgramError):
        _run(code)


class TestCycles(CycleContract, EmptyProgramContract):
    machine = staticmethod(_machine)
    run = staticmethod(_run)
    empty_program = ""
    empty_raises = "missing directive or #allocate"
    halting_program = WRAP + "#allocate a\na += 3; while (a) { a -= 1; }"
    looping_program = WRAP + "#allocate a\na += 1; while (a) { }"
