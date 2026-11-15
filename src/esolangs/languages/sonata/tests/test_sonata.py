"""Tests for the Sonata interpreter."""

import pytest

from esolangs import ExecutionLimits, ExecutionResult, Language
from esolangs.exceptions import HaltError
from esolangs.languages.sonata.interpreter import _Machine, run
from esolangs.runtime.io import IO, ScriptedIO
from esolangs.vm import _capture_workspace, complete_vm


def _step(code: str, text: str) -> str:
    machine = _Machine(code, ScriptedIO(text))
    machine.step()
    return machine.text


def test_the_page_duplicates_the_first_character() -> None:
    from esolangs.languages.sonata.tests.oracle_checks import check_raw_sonata

    check_raw_sonata()
    assert _step("^A_B->^A^A_B", "abc") == "aabc"


def test_the_page_binds_the_shortest_substrings() -> None:
    """The page's ``aabb`` gives ``,ab``, not ``a,b``."""
    assert _step("_Aa_Bb->_A,_B", "aabb") == ",ab"


def test_one_trailing_newline_leaves_the_input(monkeypatch) -> None:
    io = ScriptedIO("ab\n")
    run("ab->ok", io)
    assert io.getvalue() == "ok"

    from esolangs.languages.sonata import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Sonata",
        "ab->ok",
        interpreter,
        "_parse",
        monkeypatch,
        cases=(("ab\n", "ok"), ("Z\n", "Z"), ("Q\n", "Q")),
    )

    language = Language("Sonata")
    source, answer = "A->BC", "BC"
    limits = ExecutionLimits(max_steps=2)
    expected = language.run(source, stdin="A", limits=limits)
    assert (expected.output, expected.steps) == (answer, 2)
    write = ScriptedIO.print_str
    for accepted in range(len(answer) + 1):
        attempts = []

        def interrupt(io, text, _attempts=attempts, _accepted=accepted):
            _attempts.append(text)
            if len(_attempts) == 1:
                write(io, text[:_accepted])
                raise HaltError("temporary writer refusal")
            write(io, text)

        with monkeypatch.context() as port:
            port.setattr(ScriptedIO, "print_str", interrupt)
            debugger = language.make_debugger(source, stdin="A")
            with pytest.raises(HaltError, match="temporary writer refusal") as failure:
                debugger.run(limits=limits)
            partial = ExecutionResult(answer[:accepted], 1, 1, 0, steps=1)
            assert failure.value.observation == debugger.observation == partial
            assert debugger.snapshot() == (answer, False, False, accepted)
            state = _capture_workspace(debugger.vm)
            assert state.parts[-1].kind == "pending_output"
            assert state.parts[-1].values == (accepted,)
            if accepted == 1:
                debugger.step()
            else:
                assert debugger.run(limits=ExecutionLimits(max_steps=1)) == "halted"
            assert debugger.observation == expected
            assert complete_vm(debugger.vm, max_steps=0) == answer
            assert failure.value.observation == partial
            assert attempts == (
                [answer, answer[accepted:]] if accepted < 2 else [answer]
            )

    bare = IO()
    attempts = []
    with monkeypatch.context() as port:
        port.setattr(bare, "input_all", lambda: "A")

        def refuse(text):
            attempts.append(text)
            raise HaltError("temporary writer refusal")

        port.setattr(bare, "print_str", refuse)
        machine = _Machine(source, bare)
        machine.step()
        with pytest.raises(HaltError, match="temporary writer refusal"):
            machine.step()
        assert machine.snapshot() == (answer, True, False)
        port.setattr(bare, "print_str", attempts.append)
        machine.step()
        assert machine.snapshot() == (answer, True, True)
        assert attempts == [answer, answer]


def test_a_later_arrow_is_literal() -> None:
    io = ScriptedIO("a")
    run("a->b->c", io)
    assert io.getvalue() == "b->c"
