"""The API carries enough to use a language it has never heard of.

This is the whole point of ``describe``, ``encode_inputs``, ``instantiate``
and ``read_answer``: a caller should be able to generate a program, feed it,
and judge its answer **without a single per-language branch**.  Five rounds
of blind usability testing kept finding the same failure -- a fact that
existed only in this test suite, so a reader outside it got a confident
wrong answer -- and each fix moved one more fact into the package.

The verifier below is the measure of that.  It knows no language names, no
alphabets, no dump layouts, no halting conventions.  It reached 58 of 60
when ``answer_mode`` said only *that* a language dumps its state; the last
two needed ``read_answer`` to say *where* in the dump the answer sits.
"""

from __future__ import annotations

import pytest

import esolangs
from tests.divergence import terminates

#: One two-input table, one asymmetric two-input table, and two three-input
#: ones.  The asymmetry matters: a verifier that reads the wrong position
#: can still pass a palindromic table by luck.
_TABLES = ("0110", "0001", "10010110", "00010111")

#: The fallback for a termination-answering language with no snapshot, and
#: only that -- :func:`_terminates` prefers a proof.  A clock cannot tell a
#: loop from a slow run, so every second spent here was dead wall time that
#: bought no evidence: the run had already decided, and the bound only said
#: how long the suite sat still.  That block was 152s of this file at the
#: old 5.0-second bound and ~42s at 1.0; against a certificate it is 0.014s
#: for every row of every table, and the answer is proved rather than timed.
#:
#: Kept for a language that cannot be stepped, where the floor is still the
#: slowest *halting* row -- a 0-row over the bound would be misread as a
#: loop.  Measured across 123, ArrowQueue, Crement and Vandevelo over all
#: four tables below: 0.000s, every one sub-millisecond.  A second is three
#: orders of magnitude of headroom, which survives CI's slower cores.
_TERMINATION_TIMEOUT = 1.0
_RUN_TIMEOUT = 30.0

#: Step cap on the divergence certificate, matching
#: :func:`~esolangs.vm.run_until_halt_or_growth`'s own 100_000.  Every row
#: these sweeps ask about resolves in well under a millisecond, so this is
#: not a bound anyone is near; it is there because a *cycle* detector does
#: not return on divergence-by-growth, and a wrapping bug can produce one.
#: Reaching it is not a verdict -- the caller falls back to the clock.
_CYCLE_STEPS = 100_000


def _terminates(name: str, source: str, stdin: str) -> str:
    """``"0"`` if ``source`` halts, ``"1"`` if it provably does not.

    A termination-answering language proves a 1 by looping forever, and the
    obvious way to read that is a stopwatch: run it, and call a timeout a
    loop.  That is not evidence.  A timeout says the program had not
    finished yet, which is also what a slow run says, so the bound has to be
    guessed high enough to be safe and then paid on every 1-row -- ~42s
    across the four tables here, all of it spent waiting for a clock rather
    than deciding anything.

    :func:`~esolangs.vm.run_until_halt_or_cycle` decides it instead: a
    repeated snapshot *proves* the machine can never halt.  Over 123,
    ArrowQueue, Crement and Vandevelo -- every termination language with a
    boolean generator -- it returns the right answer for all four tables in
    0.014s total, with no row over 0.3ms.

    This stays free of per-language knowledge, which is the point of the
    file: the choice is on ``answer_mode`` and on whether the machine
    offers a snapshot, never on a name.  A language whose divergence is
    unbounded *growth* rather than a cycle would not repeat a state, so the
    detector would not return; that is the band's hard ceiling in
    `tests/duration_policy.py`, which fails such a row by name instead of
    letting it hang unattributed.  A language with no snapshot protocol at
    all falls back to the clock below.
    """
    return "0" if terminates(name, source, stdin, _TERMINATION_TIMEOUT) else "1"


def _verify(name: str, table: str) -> str:
    """Return what ``name``'s program answers on every row of ``table``.

    Deliberately free of per-language knowledge: every branch below is on a
    value :func:`esolangs.describe` reports, never on a language name.
    """
    facts = esolangs.describe(name)
    inputs = len(table).bit_length() - 1
    program = esolangs.generate(name, table)
    got = ""
    for row in range(len(table)):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        if facts["parameterized"]:
            source, stdin = esolangs.instantiate(name, program, bits), ""
        else:
            source, stdin = program, esolangs.encode_inputs(name, bits)
        if facts["answer_mode"] == "termination":
            got += _terminates(name, source, stdin)
        else:
            output = esolangs.run(name, source, stdin=stdin, timeout=_RUN_TIMEOUT)
            got += esolangs.read_answer(name, output)
    return got


@pytest.mark.slow
@pytest.mark.parametrize("table", _TABLES)
def test_every_language_verifies_with_no_per_language_knowledge(table: str) -> None:
    """Every language, driven only by what the API reports about each."""
    wrong = {}
    for name in esolangs.list_languages():
        if not esolangs.describe(name)["boolean_generator"]:
            continue
        got = _verify(name, table)
        if got != table:
            wrong[name] = got
    assert wrong == {}, (
        f"{len(wrong)} language(s) did not compute {table} through the "
        f"generic path; a fact they need is still not on the API: {wrong}"
    )


class TestTheFactsThatMakeItPossible:
    """Each of these was a wrong answer a blind reader hit."""

    def test_a_dump_says_where_its_answer_is(self) -> None:
        """``answer_mode`` said a language dumps, never where to look."""
        assert esolangs.describe("RAM0")["answer_pattern"] == r"z: (\d+)"
        assert esolangs.describe("A Painter Ant")["answer_encoding"] == ("o", "@")

    def test_reading_a_dump_needs_no_parsing_by_the_caller(self) -> None:
        ram0 = "z: 1\nn: 1\nram: {\n    0: 0,\n    1: 1\n}"
        assert esolangs.read_answer("RAM0", ram0) == "1"
        assert esolangs.read_answer("RAM0", ram0.replace("z: 1", "z: 0")) == "0"

    def test_a_termination_language_refuses_to_be_read(self) -> None:
        """Its output is not the answer, so inventing one would be a lie."""
        with pytest.raises(esolangs.ArgumentError, match="answers by terminating"):
            esolangs.read_answer("123", "VO")

    def test_an_unreadable_output_is_reported_not_guessed(self) -> None:
        with pytest.raises(esolangs.ProgramError, match="no answer this could read"):
            esolangs.read_answer("brainfuck", "no digits here!")

    def test_a_timeout_is_distinguishable_from_a_faulting_halt(self) -> None:
        """``except HaltError`` would score an invalid-op halt as a 1."""
        with pytest.raises(esolangs.ExecutionTimeoutError) as exc:
            esolangs.run("brainfuck", "+[]", timeout=0.01)
        assert isinstance(exc.value, esolangs.HaltError)
        assert isinstance(exc.value, TimeoutError)
