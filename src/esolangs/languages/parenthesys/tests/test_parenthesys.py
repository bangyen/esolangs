"""Tests for the Parenthesys interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.parenthesys.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO

_TRUTH = "[$|a]{[a]|(1)}(0)"
_BOTTLES = (
    "[99|x]{[gt|x|1]|([x] bottles of beer on the wall, [x] bottles of beer. "
    "Take one down, pass it around, )[[-|[x]|1]|x]([x] bottles of beer on the "
    "wall.)}(1 bottle of beer on the wall, 1 bottle of beer. Take one down, pass "
    "it around, No bottles of beer on the wall.)"
)
_QUINE_DATA = [
    40, 123, 91, 108, 116, 124, 91, 120, 93, 124, 56, 56, 93, 124, 92, 91, 91,
    91, 120, 93, 93, 92, 124, 91, 120, 93, 92, 93, 93, 124, 120, 91, 91, 43,
    124, 91, 120, 93, 124, 49, 93, 124, 120, 93, 93, 125, 123, 91, 108, 116,
    124, 91, 120, 93, 124, 56, 56, 93, 93, 91, 99, 104, 114, 124, 91, 120, 93,
    124, 93, 93, 124, 121, 91, 91, 43, 124, 91, 120, 93, 124, 49, 93, 124, 120,
    93, 93, 125, 41,
]  # fmt: skip
_QUINE = (
    "".join(f"[{c}|{i}]" for i, c in enumerate(_QUINE_DATA))
    + r"({[lt|[x]|88]|\[[[x]]\|[x]\][|x[[+|[x]|1]|x]]}"
    + "{[lt|[x]|88]|[chr|[x]|][|y[[+|[x]|1]|x]]})"
)


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_wiki_hello_cat_and_a_plus_b() -> None:
    assert _run("(Hello, world!)") == "Hello, world!"
    assert _run("($)", "abc 12\n") == "abc 12"
    assert _run("([+|$|$])", "2\n3\n") == "5"


def test_wiki_truth_machine() -> None:
    assert _run(_TRUTH, "0\n") == "0"
    machine = _Machine(_TRUTH, ScriptedIO("1\n"))
    for _ in range(200):
        machine.step()
    assert not machine.halted
    assert set(machine.io.getvalue()) == {"1"}


def test_wiki_99_bottles_needs_the_variable_read() -> None:
    """As written, ``[gt|x|1]`` compares the letter x."""
    with pytest.raises(HaltError, match="TypeError: 'x'"):
        _run(_BOTTLES)
    out = _run(_BOTTLES.replace("[gt|x|1]", "[gt|[x]|1]"))
    assert out.startswith("99 bottles of beer on the wall, 99 bottles of beer.")
    assert "pass it around, 2 bottles of beer on the wall." in out
    assert out.endswith("No bottles of beer on the wall.")
    assert out.count("Take one down") == 99


def test_wiki_quine_prints_only_its_data_half() -> None:
    """Its second loop starts with x already 88."""
    out = _run(_QUINE)
    assert len(out) == 643
    assert _QUINE.startswith(out)


def test_wiki_bct_interpreter_leaves_a_bracket_open() -> None:
    with pytest.raises(ValueError, match="unmatched"):
        _run("{[gt|[y]|0]|[[/|[-|[y]|[c]|4]|y][+*|c|x]}")


def test_concatenation_is_a_number_when_a_part_is() -> None:
    """In any grouping: ``1.`` alone is a string, ``<5>`` a string."""
    assert _run("[1.<5>|v]([tpe|[v]|1])([tpe|<1><2>|1])") == "10"
    assert _run(r"([tpe|\1|1])([tpe|a1|a])") == "01"


def test_numbers_keep_their_text_and_results_are_plain() -> None:
    assert _run("(007)([+|007|1])([*|1.5|2])([-|1|1.0])") == "007830"
    assert _run("([/|1|3])") == "0." + "3" * 28
    assert _run("([^|2|-2])([^|0|0])([^|2|100])") == "0.251" + str(2**100)
    assert _run("([%|-7|3])([%|7|-3])") == "2-2"


def test_functions_have_one_namespace_and_see_globals() -> None:
    assert _run("[5|g][f|a|b|[+|[a]|[g]]]([f|2|3])") == "7"
    # The inner call overwrites the caller's n before it prints.
    recursive = "[f|n|z|{[n]|[[-|[n]|1]|n][f|0|0]}([n])]"
    assert _run(recursive + "[f|2|0]") == "00"
    assert _run("([undefined|1|2])([f|a|b|z])") == "f"


def test_loops_concatenate_and_stop_on_any_zero_text() -> None:
    assert _run("[3|i]({[i]|[[-|[i]|1]|i]})") == "210"
    assert _run("[<0.0>|z]({[z]|x})({|y})") == ""


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("(ab", "unmatched"),
        ("a)", "unmatched"),
        ("(a|b)", "'|'"),
        ("[a|b|c|d|e]", "'|'"),
        ("{a|b|c}", "'|'"),
        ("ab\\", "trailing"),
    ],
)
def test_malformed_sources_are_rejected(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _run(code)


def test_runtime_errors() -> None:
    with pytest.raises(HaltError, match="AccessError"):
        _run("[gt|x|y|1]")
    with pytest.raises(HaltError, match="index 3"):
        _run("([ind|3|abc])")
    with pytest.raises(HaltError, match="needs an integer"):
        _run("([chr|65.5|])")
