"""Unexecuted owned positive controls for commit and constructor phases."""

# ruff: noqa: PT017 -- Exact raw/wrapped failure phases share one direct observer.

import sys
from unittest.mock import patch

from esolangs import ExecutionLimits
from esolangs.runtime.io import ScriptedIO

from . import oracle_checks as checker
from .fargo_corpus import Case, cases
from .fargo_model import State, model


def check_phases():
    saved = sys.get_int_max_str_digits()
    counts = {"format_phases": 0, "writer_routes": 0, "constructor_uncapped": 0}
    try:
        # Explicit positive limit, independent of the caller's default policy.
        sys.set_int_max_str_digits(640)
        for name in ("pure-diagnostic-limit", "postcommit-decimal-limit"):
            case = next(case for case in cases() if case.name == name)
            rows = model(case.source, case.stdin, case.cap)
            at = next(i for i, row in enumerate(rows) if row.error)
            assert rows[at].error == "limit"
            assert at > 0
            if name == "pure-diagnostic-limit":
                assert rows[at].state == rows[at - 1].state
                assert rows[at].output == rows[at - 1].output == ""
            else:
                assert rows[at].state != rows[at - 1].state
                assert rows[at].state.output == 0
                assert rows[at - 1].state.output != 0
                assert rows[at].output == rows[at - 1].output == "0"
            checker.check_case(case)
            counts["format_phases"] += 1
        case = Case("$", "9" * 5000 + " remainder")
        rows = model(case.source, case.stdin, case.cap)
        assert rows[0].state.number == 10**5000 - 1
        assert (rows[0].cursor, rows[0].reads, rows[0].past_end) == (5000, 1, 0)
        checker.check_case(case)
        counts["constructor_uncapped"] += 1
    finally:
        sys.set_int_max_str_digits(saved)
    assert sys.get_int_max_str_digits() == saved
    # A refused physical write is after the committed $ token, unlike a pure
    # prefix/type/arity refusal. The finish step must not retry that output.
    case = Case("$", "7 trailing")
    rows = model(case.source, case.stdin, case.cap)
    at = next(i for i in range(1, len(rows)) if rows[i].output != rows[i - 1].output)
    prior, landed = rows[at - 1], rows[at]
    marker = "Fargo injected writer refusal"
    writes = []

    def refuse(_self, value):
        assert type(value) is int
        assert value == 0
        writes.append(value)
        raise ValueError(marker)

    with patch.object(ScriptedIO, "_write", refuse):
        io = ScriptedIO(case.stdin)
        raw = checker._Machine(case.source, io)
        artifact = checker.esolangs.ProgramArtifact(case.source, "Fargo")
        vm = checker.make_vm("Fargo", artifact, stdin=case.stdin)
        debugger = checker.make_debugger("Fargo", artifact, stdin=case.stdin)
        for route, machine in enumerate((raw, vm, debugger)):
            for _ in range(at - 1):
                machine.step()
            try:
                machine.step()
            except Exception as caught:
                assert type(caught) is (
                    ValueError if route == 0 else checker.esolangs.ProgramError
                )
                assert str(caught) == marker
                if route:
                    seen = caught.observation
                    assert caught.partial_output == prior.output
                    assert seen is not None
                    checker.assert_exact(
                        seen,
                        checker.esolangs.ExecutionResult(
                            prior.output,
                            landed.cursor,
                            landed.reads,
                            landed.past_end,
                            None,
                            at - 1 if route == 2 else None,
                        ),
                    )
            else:
                raise AssertionError("writer refusal swallowed")
            inner = (
                raw
                if route == 0
                else vm._machine
                if route == 1
                else debugger.vm._machine
            )
            actual = State(
                inner.number,
                inner.output,
                inner.ind,
                tuple(checker.actual_frame(f) for f in inner.frames),
            )
            checker.assert_exact(actual, landed.state)
            before = len(writes)
            machine.step()
            assert machine.halted
            assert len(writes) == before
            counts["writer_routes"] += 1
        checker.assert_exact(
            debugger.observation,
            checker.esolangs.ExecutionResult(
                prior.output,
                landed.cursor,
                landed.reads,
                landed.past_end,
                checker.REPORT,
                at,
            ),
        )
        assert (io.getvalue(), io.position(), io.progress(), io.reads, io.past_end) == (
            prior.output,
            landed.cursor,
            landed.cursor,
            landed.reads,
            landed.past_end,
        )
        try:
            # In-process: a timeout would move the run out of the patched writer.
            checker.esolangs.run(
                "Fargo",
                artifact,
                stdin=case.stdin,
                limits=ExecutionLimits(max_steps=64),
            )
        except checker.esolangs.ProgramError as caught:
            assert type(caught) is checker.esolangs.ProgramError
            assert str(caught) == marker
            assert caught.partial_output == prior.output
            checker.assert_exact(
                caught.observation,
                checker.esolangs.ExecutionResult(
                    prior.output,
                    landed.cursor,
                    landed.reads,
                    landed.past_end,
                    None,
                    steps=at - 1,
                ),
            )
        else:
            raise AssertionError("public writer refusal swallowed")
        counts["writer_routes"] += 1
    assert len(writes) == 4
    assert all(type(value) is int and value == 0 for value in writes)
    return counts
