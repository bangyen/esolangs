"""Algebraic Programming Language through the shared API, CLI and machinery."""

from dataclasses import replace

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import run
from esolangs.vm import make_vm, run_until_halt_or_ancestor
from tests.support.reference import REFERENCE
from tests.support.vm_support import (
    assert_interrupted_input_scan_retry,
    assert_rejected_output_retry,
)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("stdin", "error_type", "message", "position", "reads", "past_end", "pending"),
    [
        (
            "2 oops 9 8",
            esolangs.HaltError,
            "input 'oops' is not a number",
            6,
            2,
            0,
            "oops",
        ),
        ("2", esolangs.InputExhaustedError, "past the end", 1, 1, 1, None),
    ],
)
def test_retried_line_bindings_keep_the_original_input(
    stdin, error_type, message, position, reads, past_end, pending, monkeypatch
) -> None:
    api = esolangs.Language("Algebraic Programming Language")
    source = "a + b"
    result = api.run(source, stdin="2 3").unwrap()
    assert (result.output, result.input_position, result.input_reads) == ("5\n", 3, 2)
    for outcome in (
        api.run(source, stdin=stdin),
        api.prepare(source).run(stdin=stdin),
        api.run(source, stdin=stdin, isolated=True),
    ):
        assert type(outcome.error) is error_type
        assert message in str(outcome.error)
        assert outcome.observation == esolangs.ExecutionResult(
            "", position, reads, past_end
        )

    dbg = api.make_debugger(source, stdin=stdin)
    for attempt, resume in enumerate((dbg.step, dbg.run, dbg.step), 1):
        with pytest.raises(error_type, match=message) as caught:
            resume()
        assert caught.value.observation == esolangs.ExecutionResult(
            "", position, reads, attempt * past_end, steps=0
        )
        assert dbg.ip == (0,)
        assert dbg.memory == []
        assert dbg.snapshot()[-1] == ((("integer", 2),), pending)
    assert_rejected_output_retry(
        "Algebraic Programming Language",
        "a + 1",
        "42\n",
        "42\n",
        prefix=6,
        stdin="41\n",
        unchanged_if_unwritten=True,
        following_writes=(),
        monkeypatch=monkeypatch,
    )
    assert_interrupted_input_scan_retry(
        api.name, "a + 1", "41\n", "42\n", "token", 0, monkeypatch
    )


class TestTheVmPathRefusesLikeRunDoes:
    """``run`` translated an interpreter's exceptions and the VM did not."""

    JUNK = ("]", "}", ")", "ZZZ", "[", "\x00")

    @pytest.mark.parametrize("entry", ["make_vm", "make_debugger"])
    def test_a_malformed_program_is_a_program_error(self, entry: str) -> None:
        """The one-character case, on the language it was reported for."""
        with pytest.raises(esolangs.ProgramError, match="unmatched"):
            getattr(debugger_api, entry)(REFERENCE, "]")

    @pytest.mark.medium
    def test_no_language_leaks_anything_else(self) -> None:
        """Every language against six kinds of junk, both entry points."""
        escapes = []
        for name in esolangs.list_languages():
            for junk in self.JUNK:
                for entry in ("make_vm", "make_debugger"):
                    try:
                        getattr(debugger_api, entry)(name, junk)
                    except esolangs.EsolangError:
                        pass
                    except Exception as exc:
                        escapes.append((name, entry, junk, type(exc).__name__))
        assert not escapes, escapes[:5]

    def test_the_two_paths_agree_on_the_class(self) -> None:
        """Not merely "both raise" -- both raise the *same* thing."""
        for entry in (debugger_api.make_vm, debugger_api.make_debugger):
            with pytest.raises(esolangs.ProgramError) as stepped:
                entry(REFERENCE, "]")
            with pytest.raises(esolangs.ProgramError) as ran:
                run(REFERENCE, "]").unwrap()
            assert str(stepped.value) == str(ran.value)

    def test_deep_source_parses_equally_across_routes(self) -> None:
        api = esolangs.Language("Algebraic Programming Language")
        limits = esolangs.ExecutionLimits(max_steps=5000)
        for source, expected in (
            ("(" * 86 + "7" + ")" * 86, "7\n"),
            ("(" * 640 + "7" + ")" * 640, "7\n"),
            ("F(x) = x\n" + "F(" * 120 + "7" + ")" * 120, "7\n"),
            ("!x = 1 - x\n" + "!" * 321 + "0", "1\n"),
            ("1**" * 320 + "1", "1\n"),
        ):
            native = api.run(source).unwrap()
            assert native.output == expected
            bounded = api.run(source, limits=limits).unwrap()
            assert replace(bounded, steps=None) == native
            assert api.run(source, isolated=True, limits=limits).unwrap() == bounded
            assert api.prepare(source).run().unwrap() == native
            debugger = api.make_debugger(source)
            assert debugger.run(limits=limits) == "halted"
            assert debugger.observation == bounded

        vm = api.make_vm("(" * 640)
        with pytest.raises(esolangs.ProgramError, match="unexpected end"):
            vm.step()


def test_the_ancestor_detector_takes_a_vm() -> None:
    """APL's truth machine, the shape the frame stack exists for."""
    truth = "x? = x & x?\nn?"
    halts = make_vm("Algebraic Programming Language", truth, stdin="0\n")
    assert run_until_halt_or_ancestor(halts) is True
    hangs = make_vm("Algebraic Programming Language", truth, stdin="1\n")
    assert run_until_halt_or_ancestor(hangs) is False
