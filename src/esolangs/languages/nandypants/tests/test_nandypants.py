"""Tests for the Nandypants interpreter."""

import pytest

from esolangs import ExecutionLimits, ExecutionResult, HaltError, Language
from esolangs.languages.nandypants.interpreter import run
from esolangs.runtime._state import WorkspaceVariant
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace
from tests.support.execution import assert_cycle_proof_replays

CAT = r"0}/>v>^<<^>^\}^0"


def _run(code: str, stdin: str = "") -> tuple[str, bool]:
    """Return the output and whether the run ended on EOF."""
    io = ScriptedIO(stdin)
    try:
        run(code, io)
    except EOFError:
        return io.getvalue(), True
    return io.getvalue(), False


def test_the_pages_cat_copies_input_until_eof() -> None:
    assert _run(CAT, "Hi!") == ("Hi!", True)
    prefix = "^" + "\\" * 8 + "v 0"
    assert_cycle_proof_replays("Nandypants", prefix, prefix + " 0", "ÿ")


def test_input_is_reduced_modulo_256(monkeypatch) -> None:
    from .oracle_checks import check_raw_nandypants

    check_raw_nandypants()
    assert _run(CAT, "Ł") == ("A", True)
    from esolangs.languages.nandypants import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Nandypants",
        r"v^/^\ ",
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("\x00", "\x01"), ("\x01", "\x00"), ("\x00", "\x01")),
    )
    _check_output_retry(monkeypatch)


def _check_output_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    api = Language("Nandypants")
    limits = ExecutionLimits(max_steps=8)
    write = ScriptedIO._write

    def check(source: str, stdin: str, output: str, accepted: int) -> None:
        clean = api.make_debugger(source, stdin=stdin)
        assert clean.run(limits=limits) == "halted"
        complete = clean.observation
        final = clean.snapshot()
        assert complete.output == output
        attempts: list[object] = []
        fault = HaltError("transient byte refusal")

        def refuse(io: ScriptedIO, char: object) -> None:
            attempts.append(char)
            if len(attempts) == 1:
                write(io, output[:accepted])
                raise fault
            write(io, char)

        with monkeypatch.context() as patch:
            patch.setattr(ScriptedIO, "_write", refuse)
            debug = api.make_debugger(source, stdin=stdin)
            with pytest.raises(HaltError, match="byte refusal") as caught:
                debug.run(limits=limits)
            assert caught.value is fault
            partial = ExecutionResult(
                output[:accepted], len(stdin), len(stdin), 0, steps=len(source) - 1
            )
            assert not debug.halted
            assert fault.observation == debug.observation == partial
            control, tape_a, tape_b, cursor, pending = debug.snapshot()
            assert (tape_a, tape_b, cursor) == final[1:]
            assert pending == (final[0], ord(output), accepted)
            assert _capture_workspace(debug.vm).parts[0] == WorkspaceVariant(
                "pending_output", (tuple(control), *pending)
            )
            assert debug.run(limits=limits) == "halted"
            assert debug.observation == complete
            assert fault.observation == partial
            assert debug.snapshot() == final
        assert attempts == [output] * (1 if accepted else 2)

    for source, stdin, output in (
        ("\\", "", "\0"),
        ("\\" * 8, "", "\0"),
        ("\\/", "A", "\0"),
        ("v^\\^", "", "\1"),
    ):
        for accepted in (0, 1):
            check(source, stdin, output, accepted)


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        (r"^\ ", "", "\x01"),  # NAND(0,0)=1; a partial byte is zero padded
        (r"^^\ v^\ ", "", "\x01"),  # a stays 1 while b=0, clears once b=1
        (r"/\ ", "\x01", "\x00"),  # a read sets b, never a
        (r"v^/^\ ", "\x00", "\x01"),  # a=1 NAND b=0 is 1
        (r"v^/^\ ", "\x01", "\x00"),  # a=1 NAND b=1 is 0
        (r"v^}\{\ ", "", "\x02"),  # tape a's right cell is 0, the left is 1
        (r"v^<\ ", "", "\x01"),  # moving b leaves a alone
        (r"hello, world", "", ""),  # other characters are ignored
        (r"3 ^\ 3 \ ", "", "\x00"),  # NAND 1: the first odd 3 jumps to the last
        (r"v^ 3 \ 3 ", "", "\x01"),  # NAND 0: it falls through
        (r"5 3 8 \ ", "", "\x00"),  # a lone label does nothing
        (r"003 ^\ 3 ", "", ""),  # 003 and 3 are one label
    ],
)
def test_commands(code: str, stdin: str, expected: str) -> None:
    assert _run(code, stdin) == (expected, False)


def test_wide_decimal_labels_ignore_the_host_digit_cap():
    from tests.support.execution import assert_digit_cap_independent

    source = "9" * 641 + "\\^" + "\u0669" * 641 + "^\\"
    assert_digit_cap_independent("Nandypants", source, "", "\x01")
