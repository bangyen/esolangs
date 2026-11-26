"""Tests for the Freestajlo interpreter."""

from dataclasses import replace

import pytest

import esolangs
from esolangs.languages.freestajlo.interpreter import run
from esolangs.runtime._state import WorkspaceVariant
from esolangs.runtime._vm_adapter import _capture_workspace
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.runner import native_runner
from tests.support.execution import assert_digit_cap_independent

_out = native_runner(run)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("1 2 3 1&::::", "2321"),  # & copies the item that deep, 0 the top
        ("5 6 7 9 2~::::", "7695"),  # ~ inserts 9 two items down
        ("1 2|:::", "221"),
        ("3 4`:", "-8"),
        ("7_3%: 7 3_%: 7_2/:", "2-2-3"),  # % takes a's sign, / truncates
        ("2 10^: 2 1_^:", "10240"),
        ('"ab":::', "97980"),  # the first character ends on top, 0 under
        ("1!5 0!(:1!$)0!(:", "05"),
        ("f{'a.}ff", "aa"),
    ],
)
def test_arithmetic_and_stack_commands(code: str, expected: str) -> None:
    assert _out(code) == expected


def test_signed_quotient_and_remainder(monkeypatch) -> None:
    from esolangs.languages.freestajlo import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Freestajlo", "f{,.} 1!0! f [tail]", interpreter, "_parse", monkeypatch
    )
    for dividend in [-(2**55 + 1), -13, -6, -1, 0, 1, 6, 13, 2**55 + 1]:
        for divisor in [-4, -3, 3, 4]:
            left = str(abs(dividend)) + "_" * (dividend < 0)
            right = str(abs(divisor)) + "_" * (divisor < 0)
            quotient = abs(dividend) // abs(divisor)
            if (dividend < 0) != (divisor < 0):
                quotient = -quotient
            assert _out(f"{left} {right}/:") == str(quotient)
            assert _out(f"{left} {right}%:") == str(dividend % divisor)


def test_rejected_freestajlo_character_preserves_its_stack_and_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = esolangs.Language("Freestajlo")
    dbg = api.make_debugger(",.,.", stdin="\ud800A")
    dbg.step()
    boundary = dbg.snapshot()
    for _ in range(2):
        with pytest.raises(
            esolangs.HaltError, match="cannot print surrogate"
        ) as caught:
            dbg.step()
        assert caught.value.observation == esolangs.ExecutionResult(
            "", 1, 1, 0, steps=1
        )
        assert dbg.snapshot() == boundary
    assert api.run(",.,.", stdin="BA").output == "BA"
    _check_output_retry(api, monkeypatch)
    _check_number_retry(api, monkeypatch)


def test_wide_decimal_operands_ignore_the_host_digit_cap():
    wide = "9" * 641
    assert_digit_cap_independent(
        "Freestajlo", f";:{wide}:", f"-{wide} ", f"-{wide}{wide}"
    )


def _check_output_retry(
    api: esolangs.Language, monkeypatch: pytest.MonkeyPatch
) -> None:
    limits = esolangs.ExecutionLimits(max_steps=8)
    write = ScriptedIO._write
    attempts: list[object] = []
    prefix = ""

    def reject_first(port: ScriptedIO, value: object) -> None:
        attempts.append(value)
        if len(attempts) == 1:
            write(port, prefix)
            raise esolangs.HaltError("temporary write refusal")
        write(port, value)

    for source, value, result in (("65.66.", "A", "AB"), ("123:65.", 123, "123A")):
        clean = api.make_debugger(source)
        assert clean.run(limits=limits) == "halted"
        assert clean.observation.output == result
        text = str(value)
        for accepted in range(len(text) + 1):
            attempts.clear()
            prefix = text[:accepted]
            replay = api.make_debugger(source)
            replay.step()
            boundary = replay.snapshot()
            before = replay.observation
            workspace = _capture_workspace(replay.vm)
            with monkeypatch.context() as scoped:
                scoped.setattr(ScriptedIO, "_write", reject_first)
                with pytest.raises(esolangs.HaltError, match="write refusal") as exc:
                    replay.step()
                partial = replace(before, output=prefix)
                assert exc.value.observation == replay.observation == partial
                if accepted:
                    instruction, *components = workspace.parts
                    assert replay.snapshot() == (*boundary, accepted)
                    assert _capture_workspace(replay.vm).parts == (
                        WorkspaceVariant("pending_output", (instruction, accepted)),
                        *components,
                    )
                else:
                    assert replay.snapshot() == boundary
                    assert _capture_workspace(replay.vm) == workspace
                assert replay.run(limits=limits) == "halted"
            suffix = [text[accepted:]] if 0 < accepted < len(text) else []
            expected_writes = [value, *suffix, "A" if value == 123 else "B"]
            if not accepted:
                expected_writes.insert(1, value)
            assert attempts == expected_writes
            assert replay.observation == clean.observation
            assert replay.snapshot() == clean.snapshot()
            assert _capture_workspace(replay.vm) == _capture_workspace(clean.vm)
            assert exc.value.observation == partial


def _check_number_retry(
    api: esolangs.Language, monkeypatch: pytest.MonkeyPatch
) -> None:
    limits = esolangs.ExecutionLimits(max_steps=8)
    read = ScriptedIO.input_char
    calls = 0
    fail_at = 0
    consume_on_failure = False

    def refuse(port: ScriptedIO, prompt: str = "Input: ") -> int:
        nonlocal calls
        calls += 1
        if calls == fail_at:
            if consume_on_failure:
                read(port, prompt)
            raise esolangs.HaltError("temporary read refusal")
        return read(port, prompt)

    for source, stdin, result, fail_at, pending, past_end in (
        (";:,.", "x-23!A", "-23A", 3, (True, ""), 0),
        (";:,.", "23!A", "23A", 2, (False, "2"), 0),
        (";:,.", "x- 23!A", "23A", 4, None, 0),
        (";:", "-23", "-23", 4, (True, "23"), 1),
        (";:", "junk-", "0", 6, (True, ""), 1),
    ):
        clean = api.make_debugger(source, stdin=stdin)
        assert clean.run(limits=limits) == "halted"
        assert clean.observation.output == result
        assert clean.observation.input_past_end == past_end
        replay = api.make_debugger(source, stdin=stdin)
        boundary = replay.snapshot()
        workspace = _capture_workspace(replay.vm)
        cursor = fail_at - 1
        calls = 0
        with monkeypatch.context() as scoped:
            scoped.setattr(ScriptedIO, "input_char", refuse)
            with pytest.raises(esolangs.HaltError, match="read refusal") as exc:
                replay.step()
            partial = esolangs.ExecutionResult("", cursor, cursor, 0, steps=0)
            assert exc.value.observation == replay.observation == partial
            assert replay.snapshot() == (
                *boundary[:-1],
                cursor,
                *((pending,) if pending else ()),
            )
            assert _capture_workspace(replay.vm).parts == (
                *workspace.parts[:-1],
                WorkspaceVariant("pending_number", (cursor, *pending))
                if pending
                else cursor,
            )
            assert replay.run(limits=limits) == "halted"
        assert replay.observation == clean.observation
        assert replay.snapshot() == clean.snapshot()
        assert _capture_workspace(replay.vm) == _capture_workspace(clean.vm)
        assert exc.value.observation == partial

    replay = api.make_debugger(";:", stdin="-23")
    fail_at, calls, consume_on_failure = 3, 0, True
    monkeypatch.setattr(ScriptedIO, "input_char", refuse)
    with pytest.raises(esolangs.HaltError, match="read refusal") as first:
        replay.step()
    stopped = replay.snapshot()
    partial = esolangs.ExecutionResult("", 3, 3, 0, steps=0)
    assert first.value.observation == partial
    for _ in range(2):
        with pytest.raises(esolangs.HaltError, match="read refusal") as retry:
            replay.step()
        assert retry.value is not first.value
        assert retry.value.observation == partial
        assert replay.snapshot() == stopped
    assert calls == 3
