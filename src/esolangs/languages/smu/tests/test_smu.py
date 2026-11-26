"""Smu: the wiki cat, command edges, the preprocessor, and generated programs."""

from functools import partial

import pytest

from esolangs import ExecutionLimits, ExecutionResult, Language
from esolangs.exceptions import HaltError
from esolangs.languages.smu.generator import smu
from esolangs.languages.smu.interpreter import preprocess, run
from esolangs.runtime._state import WorkspaceVariant
from esolangs.runtime._vm_adapter import _capture_workspace
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import complete_vm
from tests.interpreters.runner import native_runner
from tests.support.witness_tables import witnesses

CAT = "x(+|)xg()+gy(g)ybx=(=)y=xy+x=ba(bxggxg)aa(|=)=a(+=)=baxg"
_A = "((+|)=(=)(()+)=(+|)(()+)+(+|)=(+|)()+()+(+|)()+)"
#: The wiki's "expanded form" drops the ``=`` after ``(+=)``.
PRINTED = f"{_A}(|=)={_A}(+=)(+|)=(=)(()+)=(+|)(()+)+(+|)={_A}(+|)()+"
REPAIRED = PRINTED.replace("(+=)(+|)", "(+=)=(+|)")


_run = native_runner(run)


def test_wiki_cat_copies_every_byte() -> None:
    from .oracle_checks import check_raw_smu

    check_raw_smu()
    text = "".join(map(chr, range(256)))
    assert _run(CAT, text) == text
    assert _run(CAT) == ""


def test_wiki_expanded_form_is_the_cat_less_one_equals(monkeypatch) -> None:
    """The compact source fixes the repair; the printed form forces a 1 first."""
    assert preprocess(CAT) == REPAIRED
    assert _run(PRINTED, "\x00") == "\x01"
    assert _run(PRINTED, "\x02") == "\x03"

    from esolangs.languages.smu import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Smu",
        "m()|m & a comment\nm",
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("A", "\x01"), ("B", "\x00"), ("C", "\x01")),
    )


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        # ``=`` assigns the second string to the top's name; ``+`` reads an
        # unset ``""`` as empty.
        ("(+)(|)=(|)()+", "", "\x01"),
        # ``|`` leaves the head on top: ``|`` is assigned ``+``, not ``||``.
        ("(+||)|(|)=(|)()+", "", "\x01"),
        ("()|(+)", "", "\x01"),  # an empty string is popped, nothing pushed
        ("=+", "", ""),  # underflow is a no-op; EOF's ``=`` prints nothing
        ("()=|", "", ""),
        ("", "A", "\x01"),  # the run's bit is the byte's low bit
        ("", "\x02", "\x00"),
        ("1a(+)1a & a comment\n 1a", "", "\x01"),
        ("7(+)", "", "\x01"),  # digits naming no macro are dropped
    ],
)
def test_commands(code: str, stdin: str, expected: str) -> None:
    assert _run(code, stdin) == expected


@pytest.mark.parametrize(
    ("code", "match"),
    [
        ("(+", r"unmatched '\('"),
        (")", r"unmatched '\)'"),
        ("a(b)a", "defined inside macro"),
        ("a(+)", "never closed"),
    ],
)
def test_malformed_source(code: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _run(code)


@pytest.mark.parametrize(
    "code",
    [
        "((()+))|",  # outputs ``(``
        "((()+))|(())=(+)",  # runs ``()+)``
    ],
)
def test_runtime_halts(code: str) -> None:
    with pytest.raises(HaltError):
        _run(code)


@pytest.mark.parametrize("debugger", [False, True])
@pytest.mark.parametrize(
    ("code", "message", "output", "stack", "phase", "steps"),
    [
        ("(())", "cannot output", "", ("=", "()"), False, 2),
        ("(())|(+|||||+|)", "is unbalanced", "A", ("=", ")", "("), None, 4),
    ],
)
def test_failed_run_boundary_can_be_retried(
    code, message, output, stack, phase, steps, *, debugger: bool
) -> None:
    api = Language("Smu")
    limits = ExecutionLimits(max_steps=6)
    if debugger:
        debug = api.make_debugger(code)
        vm = debug.vm
        drive = partial(debug.run, limits=limits)
    else:
        vm = api.make_vm(code)
        drive = partial(complete_vm, vm, max_steps=6)
    snapshots = []
    for completed in (steps, 0):
        with pytest.raises(HaltError, match=message) as stopped:
            drive()
        assert not vm.halted
        assert stopped.value.partial_output == vm.output == output
        assert stopped.value.observation == ExecutionResult(
            output, 0, 0, 1, steps=steps if debugger else completed
        )
        snapshots.append((vm.snapshot(), _capture_workspace(vm)))
    assert snapshots[0] == snapshots[1]
    assert vm.stack == list(stack)
    _, workspace = snapshots[0]
    parts = dict(zip(workspace.model.components, workspace.parts, strict=True))
    assert parts["fresh"] is phase
    assert parts["stack"] == stack


def test_valid_run_boundary_halts_at_the_exact_budget(monkeypatch) -> None:
    vm = Language("Smu").make_vm("(+)")
    assert complete_vm(vm, max_steps=6) == "\x01"
    assert vm.halted
    _check_output_retry(monkeypatch)


def _check_output_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    language = Language("Smu")
    write = ScriptedIO._write
    for source, output, refused, steps, eof, offset, buffered in (
        ("(+)", "\x01", 0, 5, 2, 0, (1, 1)),
        ("(++++++++||||||||+)", "ÿ\0\x01", 1, 2, 1, 15, (0, 7)),
        ("((++++++++))(+)", "ÿ\x01", 0, 6, 2, 6, (127, 7)),
    ):
        limits = ExecutionLimits(max_steps=10)
        expected = language.run(source, limits=limits)
        assert expected.output == output
        for accepted in (0, 1):
            calls = []

            def refuse(io, value, *, log=calls, at=refused, count=accepted):
                log.append(value)
                if len(log) == at + 1:
                    write(io, value[:count])
                    raise HaltError("temporary writer refusal")
                write(io, value)

            with monkeypatch.context() as port:
                port.setattr(ScriptedIO, "_write", refuse)
                dbg = language.make_debugger(source)
                with pytest.raises(
                    HaltError, match="temporary writer refusal"
                ) as fault:
                    dbg.run(limits=limits)
                partial_result = ExecutionResult(
                    output[: refused + accepted],
                    0,
                    0,
                    eof,
                    steps=steps,
                )
                assert fault.value.observation == dbg.observation == partial_result
                workspace = _capture_workspace(dbg.vm)
                parts = dict(
                    zip(workspace.model.components, workspace.parts, strict=True)
                )
                outgoing, used = buffered
                assert parts["outgoing"] == outgoing
                if offset or accepted:
                    assert parts["used"] == WorkspaceVariant(
                        "pending_output", (used, offset, accepted)
                    )
                    assert dbg.snapshot()[-1] == (offset, accepted)
                else:
                    assert parts["used"] == used
                assert not dbg.halted
                assert dbg.run(limits=limits) == "halted"
                assert dbg.observation == expected
                assert fault.value.observation == partial_result
            attempt = (
                output
                if accepted
                else output[:refused] + output[refused] + output[refused:]
            )
            assert calls == list(attempt)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_generated_programs(n: int) -> None:
    for table in witnesses(n):
        code = smu(table)
        for row in range(1 << n):
            assert _run(code, f"{row:0{n}b}") == table[row], (table, row)


def test_a_repeated_subtree_is_written_once() -> None:
    # Sixteen copies of one 16-row block: the block's tree is a macro, so the
    # program is the block's plus a name a copy, not sixteen trees.
    block = "0110100110010110"
    table = block * 16
    code = smu(table)
    assert len(code) < len(smu(block)) + 16 * 8
    for row in range(0, 256, 17):
        assert _run(code, f"{row:08b}") == table[row], row
