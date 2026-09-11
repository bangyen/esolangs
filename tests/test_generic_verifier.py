"""The API carries enough to use a language it has never heard of.

This is the whole point of ``describe``, ``encode_inputs``, ``instantiate``
and ``read_answer``: a caller should be able to generate a program, feed it,
and judge its answer **without a single per-language branch**.  Five rounds
of blind usability testing kept finding the same failure -- a fact that
existed only in this test suite, so a reader outside it got a confident
wrong answer -- and each fix moved one more fact into the package.

The verifier below is the measure of that.  It knows no language names, no
alphabets, no dump layouts, no halting conventions.  It reached 67 of 69
when ``answer_mode`` said only *that* a language dumps its state; the last
two needed ``read_answer`` to say *where* in the dump the answer sits.
"""

from __future__ import annotations

import pytest

import esolangs

#: One two-input table, one asymmetric two-input table, and two three-input
#: ones.  The asymmetry matters: a verifier that reads the wrong position
#: can still pass a palindromic table by luck.
_TABLES = ("0110", "0001", "10010110", "00010111")

#: A termination-answering language proves a 1 by *not* halting, so this is
#: paid once per such row.  Three languages, so the floor is real but small.
_TERMINATION_TIMEOUT = 5.0
_RUN_TIMEOUT = 30.0


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
            try:
                esolangs.run(name, source, stdin=stdin, timeout=_TERMINATION_TIMEOUT)
                got += "0"
            except esolangs.ExecutionTimeoutError:
                got += "1"
        else:
            output = esolangs.run(name, source, stdin=stdin, timeout=_RUN_TIMEOUT)
            got += esolangs.read_answer(name, output)
    return got


@pytest.mark.slow
@pytest.mark.parametrize("table", _TABLES)
def test_every_language_verifies_with_no_per_language_knowledge(table: str) -> None:
    """All 69, driven only by what the API reports about each."""
    wrong = {}
    for name in esolangs.list_languages():
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
        assert esolangs.describe("A Painter Ant")["answer_values"] == ("o", "@")

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
            esolangs.run("brainfuck", "+[]", timeout=1)
        assert isinstance(exc.value, esolangs.HaltError)
        assert isinstance(exc.value, TimeoutError)
