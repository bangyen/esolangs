"""Tests for the Stisp interpreter."""

from itertools import product

from esolangs.languages.stisp.interpreter import _Machine, run
from esolangs.languages.stisp.tests.oracle_checks import check_raw_stisp
from esolangs.runtime.io import ScriptedIO


def _result(code: str) -> str:
    io = ScriptedIO()
    run(code, io)
    return io.getvalue()


def test_the_first_matching_equation_wins(monkeypatch) -> None:
    check_raw_stisp()
    assert _result("x -> f[] = FIRST; A -> f[] = SECOND; A -> f[]") == "FIRST"
    from esolangs.languages.stisp import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Stisp",
        "x -> f[] = FIRST; A -> f[] = SECOND; A -> f[]",
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("", "FIRST"),) * 3,
    )


def test_a_frame_rewrites_to_several_frames_in_order() -> None:
    """``b`` runs before ``c``: the right side's first frame goes on top."""
    machine = _Machine("x -> a[] = x -> b[] -> c[]; A -> a[] -> d[]", ScriptedIO())
    machine.step()
    assert machine.stack == ["A", "b", "c", "d"]


def test_list_sugar_prints_as_a_list() -> None:
    assert _result("x -> id[] = x; (A . (B . ())) -> id[]") == "(A B)"

    rules = (
        "() -> reverse[acc] = acc; "
        "(h . t) -> reverse[acc] = t -> reverse[(h . acc)]; "
        "x -> same[x] = YES; x -> same[y] = NO; "
    )
    for size in range(6):
        for values in product(("A", "B"), repeat=size):
            source = "(" + " ".join(values) + ")"
            reversed_list = "(" + " ".join(reversed(values)) + ")"
            assert _result(rules + source + " -> reverse[()]") == reversed_list
            assert _result(rules + source + f" -> reverse[()] -> same[{source}]") == (
                "YES" if values == values[::-1] else "NO"
            )

    for first, last in product(("(A)", "(B)"), repeat=2):
        source = f"({first} X {last})"
        expected = "YES" if first == last else "NO"
        assert (
            _result(rules + source + f" -> reverse[()] -> same[{source}]") == expected
        )


def test_deep_data_parses_and_prints_without_recursion() -> None:
    deep = "(" * 5000 + "A" + ")" * 5000
    assert _result(deep) == deep
