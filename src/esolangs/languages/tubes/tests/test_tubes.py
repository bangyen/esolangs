"""Tests for the Tubes interpreter."""

import unicodedata

import pytest

from esolangs.exceptions import HaltError, InputExhaustedError, ProgramError
from esolangs.languages.tubes.interpreter import _MOVERS, _Machine, run
from esolangs.runtime.io import ScriptedIO

# The page's snippets, less the one-space indent of its code blocks.
_LOOP = " ┌┐\n ◉◆\n ║║\n▶┤│\n └┘"
_SWITCH = " ┌─▷exit if mem=2\n▶┼┬▷exit if mem=0\n │└▷exit if mem=3\n └─▷exit if mem=1"
# From the Truth-machine page.
_TRUTH = "  ┌─┐\n  ├┐│\n  └◆┘\n▶◇◆┤\n  ▷┘"
_WOLFRAM = (
    "┌◉◉◉─┬─┬┐\n├─╖┌─◉─◉◉┐\n└┐└┼┐╙╕│╙╛\n▶┘ └◉─┘│\n┌───┘┌┬┘\n"
    "╘╖┌◉═╜│\n┌┘◉   ╙╕\n│┌┼◉◉──┘\n├╜└◉═╖\n└────┘"
)


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _span(cells: dict[int, int]) -> tuple[int, ...]:
    """The nonzero stretch of a tape."""
    keys = [k for k, v in cells.items() if v]
    return tuple(cells.get(k, 0) for k in range(min(keys), max(keys) + 1))


def test_movers_match_unicode_names() -> None:
    words = {"LIGHT": 1, "SINGLE": 1, "DOUBLE": 2}
    sides = {"RIGHT": (0,), "DOWN": (1,), "LEFT": (2,), "UP": (3,)}
    sides |= {"HORIZONTAL": (0, 2), "VERTICAL": (1, 3)}
    for glyph, arms in _MOVERS.items():
        name = unicodedata.name(glyph).removeprefix("BOX DRAWINGS ").split()
        want = [0] * 4
        if name[0] in words:  # "DOUBLE DOWN AND RIGHT", "LIGHT VERTICAL"
            for word in name[1:]:
                for side in sides.get(word, ()):
                    want[side] = words[name[0]]
        else:  # "DOWN SINGLE AND RIGHT DOUBLE"
            for k in range(0, len(name), 3):
                for side in sides[name[k]]:
                    want[side] = words[name[k + 1]]
        assert tuple(want) == arms, glyph
    assert len(_MOVERS) == 40


def test_the_loop_prints_0123_forever() -> None:
    io = ScriptedIO()
    machine = _Machine(_LOOP, io)
    for _ in range(200):
        machine.step()
    assert io.getvalue().startswith("0123" * 5)


@pytest.mark.parametrize(("value", "row"), [(0, 1), (1, 3), (2, 0), (3, 2)])
def test_the_switch_takes_its_labelled_exit(value: int, row: int) -> None:
    machine = _Machine(_SWITCH, ScriptedIO())
    machine.cells[(0, 0)] = value
    while not machine.halted:
        machine.step()
    assert machine.ip == (row, 3, 0)


def test_the_truth_machine() -> None:
    assert _out(_TRUTH, "0") == "0"
    io = ScriptedIO("1")
    machine = _Machine(_TRUTH, io)
    for _ in range(200):
        machine.step()
    assert not machine.halted
    assert set(io.getvalue()) == {"1"}
    assert len(io.getvalue()) > 20


def test_the_wolfram_machine_matches_the_2_3_turing_machine() -> None:
    # 3,000 cells of travel reach the tape of 152 Turing machine steps.
    machine = _Machine(_WOLFRAM, ScriptedIO())
    for _ in range(3000):
        machine.step()
    rules = {
        ("A", 0): (1, 1, "B"),
        ("A", 1): (2, -1, "A"),
        ("A", 2): (1, -1, "A"),
        ("B", 0): (2, -1, "A"),
        ("B", 1): (2, 1, "B"),
        ("B", 2): (0, 1, "A"),
    }
    tape: dict[int, int] = {}
    pos, state = 0, "A"
    for _ in range(152):
        tape[pos], move, state = rules[state, tape.get(pos, 0)]
        pos += move
    assert {y for _, y in machine.cells} == {1}
    assert _span({x: v for (x, _), v in machine.cells.items()}) == _span(tape)


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        # Non-digits are skipped; 4 is not a value.
        ("▶◇◆◇◆▷", "x4\n3 a2", "32"),
        ("▶◉◉◉◉◆▷", "", "0"),
        # A double exit moves the memory pointer; single ones do not.
        ("▶◉═◆▷", "", "0"),
        ("▶◉─◆▷", "", "1"),
        # Re-entering the start is a no-op; the second pass takes ┬'s right arm.
        ("┌▶◉◆┬▷\n│   │\n└───┘", "", "12"),
    ],
)
def test_rulings(code: str, stdin: str, expected: str) -> None:
    assert _out(code, stdin) == expected


@pytest.mark.parametrize(
    ("code", "stdin", "error", "message"),
    [
        ("◆▷", "", ProgramError, "no ▶"),
        ("▶▶▷", "", ProgramError, "2 ▶"),
        ("▶◆x", "", HaltError, "x"),
        ("▶◆", "", HaltError, " "),
        ("▶│", "", HaltError, "│"),
        ("▶◇▷", "x", InputExhaustedError, None),
    ],
)
def test_errors(
    code: str, stdin: str, error: type[Exception], message: str | None
) -> None:
    with pytest.raises(error, match=message):
        _out(code, stdin)
