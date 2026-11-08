"""Execution tests for the Thue interpreter."""

import re

import pytest

from esolangs.languages.thue import interpreter as thue
from esolangs.languages.thue.interpreter import (
    _Machine,
    _matches,
    _parse,
    prepare_machine,
    run,
)
from esolangs.languages.thue.tests.oracle_checks import check_raw_thue
from esolangs.runtime.io import ScriptedIO
from esolangs.runtime.randomness import FirstDraw, Seeded
from tests.interpreters.runner import run_program
from tests.support.factories import reject_rng_options, rng_factory
from tests.support.raises import assert_rejected_with_hint

#: Two print rules over ``ab``.  Both match the starting state, so which
#: half prints first is a *draw* -- the pair below pins both orders.
GREETING = "a::=~Hello\nb::=~ world\n::=\nab"


def test_a_rule_prints_and_deletes_its_match() -> None:
    check_raw_thue()
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

    rng, before, options, factory = rng_factory(prepare_machine, program)
    options.clear()
    first_machine, second = factory(ScriptedIO()), factory(ScriptedIO())
    assert first_machine is not second
    assert first_machine._rng is second._rng is rng
    assert first_machine._text is not second._text
    assert rng._random.getstate() == before
    initial = second.snapshot()
    first_machine.step()
    assert rng._random.getstate() != before
    assert second.snapshot() == initial
    assert second.state == "aab"
    assert first_machine.state != second.state
    reject_rng_options(prepare_machine, [], "text source", "")


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
    """Rescan overlaps independently, including matches across tiny blocks."""
    monkeypatch.setattr(thue, "_BLOCK", 3)
    monkeypatch.setattr(thue, "_GROUP", 2)
    rules = (
        ("ab", "ba"),
        ("ba", ""),
        ("bb", "abababababab"),
        ("aab", "b"),
        ("bab", "a"),
    )
    for seed in range(8):
        state = "ab" * 40
        program = "\n".join([*(f"{a}::={b}" for a, b in rules), "::=", state])
        io = ScriptedIO("unused")
        machine = _Machine(program, io, Seeded(seed))
        reference = Seeded(seed)
        for _ in range(400):
            matches = [
                (rule, offset)
                for rule, (lhs, _) in enumerate(rules)
                for offset in range(len(state))
                if state.startswith(lhs, offset)
            ]
            assert machine.state == state
            assert machine.ip == (matches[0] if matches else ())
            assert machine.halted == (not matches)
            if not matches:
                break
            rule, offset = matches[reference.randbelow(len(matches))]
            lhs, rhs = rules[rule]
            state = state[:offset] + rhs + state[offset + len(lhs) :]
            machine.step()
        assert machine.state == state
        assert io.position() == 0
        assert io.getvalue() == ""


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Thue", "a::=b", "line containing only ::=")
