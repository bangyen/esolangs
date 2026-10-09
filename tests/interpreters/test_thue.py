"""Execution tests for the Thue interpreter."""

import re

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other import thue
from esolangs.interpreters.other.thue import _advance, _Machine, _matches, _parse, run
from esolangs.interpreters.randomness import FirstDraw, Seeded
from tests.interpreters.runner import run_program
from tests.raises import assert_rejected_with_hint

#: Two print rules over ``ab``.  Both match the starting state, so which
#: half prints first is a *draw* -- the pair below pins both orders.
GREETING = "a::=~Hello\nb::=~ world\n::=\nab"


def test_a_rule_prints_and_deletes_its_match() -> None:
    assert run_program(run, "a::=~Hello\n::=\na") == "Hello"


def test_two_applicable_print_rules_can_fire_in_either_order() -> None:
    """Which one goes first is the draw, so both orders are the language."""
    assert run_program(run, GREETING, rng=FirstDraw(0)) == "Hello world"
    assert run_program(run, GREETING, rng=FirstDraw(1)) == " worldHello"


def test_a_rewrite_reaches_a_state_no_rule_matches() -> None:
    rules, state = _parse("ab::=ba\n::=\nabb")
    assert state == "abb"
    machine = _Machine("ab::=ba\n::=\nabb", ScriptedIO(""), Seeded(0))
    while not machine.halted:
        machine.step()
    assert machine.state == "bba"
    assert _matches(machine.state, rules) == ()


def test_which_rewrite_runs_is_drawn_and_a_source_fixes_it() -> None:
    """The choice is the spec's, and random: both outcomes are reachable."""
    program = "b::=~1\nab::=~2\n::=\naab"
    assert run_program(run, program, rng=FirstDraw(0)) == "1"
    assert run_program(run, program, rng=FirstDraw(1)) == "2"
    # Unseeded, the draw is real, so only the set of outcomes is pinned.
    assert {run_program(run, program) for _ in range(40)} <= {"1", "2"}


def test_every_occurrence_is_a_candidate_including_overlapping_ones() -> None:
    """``aa`` occurs twice in ``aaa``; both are draws."""
    rules, _state = _parse("aa::=b\n::=\naaa")
    assert _matches("aaa", rules) == ((0, 0), (0, 1))


def test_a_seeded_run_repeats_itself() -> None:
    program = "b::=~1\nab::=~2\n::=\naab"
    first = [run_program(run, program, rng=Seeded(5)) for _ in range(5)]
    assert len(set(first)) == 1


def test_input_is_substituted_by_the_triple_colon() -> None:
    assert run_program(run, "x::=:::\n::=\nx", "hi\n") == ""
    machine = _Machine("x::=:::\ny::=~!\n::=\nxy", ScriptedIO("hi\n"), Seeded(0))
    while not machine.halted:
        machine.step()
    assert machine.state == "hi"


def test_a_read_past_the_end_is_eof() -> None:
    with pytest.raises(EOFError):
        run_program(run, "x::=:::\n::=\nx", suppress_eof=False)


def test_the_separator_may_carry_whitespace() -> None:
    """The spec's shape: both sides empty *or entirely whitespace*."""
    rules, state = _parse("a::=b\n  ::=  \naa")
    assert rules == (("a", "b"),)
    assert state == "aa"
    # A whitespace left side with text on the right is a rule, not the end.
    assert run_program(run, "  ::=~y\n::=\na  b") == "y"


def test_an_empty_output_string_prints_a_newline() -> None:
    """Vogel's convention, which the wiki carries: ``~`` alone is a newline."""
    assert run_program(run, "a::=~\n::=\na") == "\n"


def test_a_multi_line_state_survives_parsing() -> None:
    rules, state = _parse("a::=b\n::=\nfirst\nsecond")
    assert rules == (("a", "b"),)
    assert state == "first\nsecond"


@pytest.mark.parametrize(
    ("program", "message"),
    [
        ("a::=b\na\n", "nothing but whitespace on either side"),
        ("nonsense\n::=\na", "has no '::='"),
        ("::=x\n::=\na", "empty left-hand side"),
    ],
)
def test_a_malformed_program_is_refused(program: str, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        run_program(run, program)


def test_an_empty_left_hand_side_is_refused_before_it_can_loop() -> None:
    """It would match everywhere, so no run could ever finish."""
    with pytest.raises(ValueError, match="matches everywhere"):
        _parse("::=x\n::=\na")


def test_a_program_with_no_rules_halts_at_once() -> None:
    assert run_program(run, "::=\nanything") == ""


def test_the_pointer_names_the_rule_and_its_offset() -> None:
    machine = _Machine("b::=c\n::=\nab", ScriptedIO(""), Seeded(0))
    assert machine.ip == (0, 1)
    machine.step()
    assert machine.halted
    assert machine.ip == ()


def test_the_search_covers_every_draw_and_declines_a_read() -> None:
    """The branching protocol: all successors, or ``None`` for an input rule."""
    machine = _Machine("b::=~1\nab::=~2\n::=\naab", ScriptedIO(""), Seeded(0))
    # Deleting the ``b`` at 2 leaves ``aa``; deleting the ``ab`` at 1 leaves ``a``.
    assert set(machine.branching_successors(machine.state, 10) or ()) == {"aa", "a"}
    assert not machine.branching_halted("aab")
    assert machine.branching_halted("")
    reader = _Machine("x::=:::\n::=\nx", ScriptedIO("hi\n"), Seeded(0))
    assert reader.branching_successors(reader.state, 10) is None


def test_the_branching_protocol_reports_the_state_it_searches() -> None:
    """The hang proof searches every draw, so the string is its own branching
    state and the successors are one per available rewrite."""
    machine = _Machine("a::=b\na::=c\n::=\naa", ScriptedIO(""))
    assert machine.branching_snapshot() == "aa"
    assert not machine.branching_halted("aa")
    assert machine.branching_halted("zz")
    assert set(machine.branching_successors("aa", 8)) == {"ba", "ab", "ca", "ac"}


def test_the_block_index_steps_as_the_whole_string_would(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The machine indexes occurrences per block; :func:`_matches` and
    :func:`_advance` rescan the whole string.  Tiny blocks put rewrites
    across every boundary, and ``bb``'s side outgrows two blocks."""
    monkeypatch.setattr(thue, "_BLOCK", 3)
    monkeypatch.setattr(thue, "_GROUP", 2)
    program = "ab::=ba\nba::=\nbb::=abababababab\naab::=b\nbab::=a\n::=\n" + "ab" * 40
    machine = _Machine(program, ScriptedIO(""), Seeded(4))
    rules, state = _parse(program)
    reference = Seeded(4)
    for _ in range(400):
        found = _matches(state, rules)
        assert machine.state == state
        assert machine.ip == (found[0] if found else ())
        if not found:
            break
        state = _advance(state, rules, found[reference.randbelow(len(found))])[0]
        machine.step()


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Thue", "a::=b", "line containing only ::=")
