"""Tests for the Sonata interpreter."""

import pytest

from esolangs import ExecutionLimits, ExecutionResult, Language
from esolangs.exceptions import HaltError
from esolangs.languages.sonata.interpreter import _Machine, run
from esolangs.runtime._vm_adapter import _capture_workspace
from esolangs.runtime.io import IO, ScriptedIO
from esolangs.vm import complete_vm
from tests.support.cli_support import call_both


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
    expected = language.run(source, stdin="A", limits=limits).unwrap()
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


def test_a_later_arrow_is_literal(tmp_path, capsys) -> None:
    io = ScriptedIO("a")
    run("a->b->c", io)
    assert io.getvalue() == "b->c"

    api = Language("Sonata")
    path = tmp_path / "rules"
    for separator in ("\n", "\r\n"):
        text = separator.join(("a->b->c", "b->other"))
        path.write_bytes(text.encode())
        record = api.from_json(api.to_json(path))
        assert record.source == text
        assert api.run(path, stdin="a").unwrap().output == "b->c"
        assert api.prepare(record).run(stdin="a").unwrap().output == "b->c"
        assert complete_vm(api.make_vm(text, stdin="a")) == "b->c"
        assert api.run(text, stdin="a", isolated=True).unwrap().output == "b->c"
        output = call_both(["run", api.name, str(path)], capsys, stdin="a")
        assert output == ("b->c", "")
    for text, expected in (
        ("a->b->\rc\nb->other", "b->\rc"),
        ("a->b->c\r\r\nb->other", "b->c\r"),
        ("a->b->c\r", "b->c\r"),
    ):
        assert api.run(text, stdin="a").unwrap().output == expected
