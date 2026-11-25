"""Unexecuted owned positive controls for commit and constructor phases."""

# ruff: noqa: PT017 -- Exact raw/wrapped failure phases share one direct observer.

import sys
from decimal import Decimal
from unittest.mock import patch

from esolangs import ExecutionLimits
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import assert_exact

from . import oracle_checks as checker
from .fargo_corpus import Case, cases
from .fargo_model import State, model


def check_phases():
    saved = sys.get_int_max_str_digits()
    counts = {"format_phases": 0, "writer_routes": 0, "constructor_uncapped": 0}
    try:
        # Explicit positive limit, independent of the caller's default policy.
        sys.set_int_max_str_digits(640)
        case = next(case for case in cases() if case.name == "large-array-index")
        rows = model(case.source, case.stdin, case.cap)
        at = next(i for i, row in enumerate(rows) if row.error)
        assert rows[at].error == "halt"
        message = rows[at].message
        assert message is not None
        assert message.startswith("array index ")
        assert message.endswith(" out of range")
        index = message.removeprefix("array index ").removesuffix(" out of range")
        assert int(Decimal(index)) == (1 << 20000) - 1
        assert at > 0
        assert rows[at].state == rows[at - 1].state
        assert rows[at].output == rows[at - 1].output == ""
        checker.check_case(case)
        checker.public(case, rows, isolated=True)
        counts["format_phases"] += 1

        case = next(case for case in cases() if case.name == "large-decimal-output")
        rows = model(case.source, case.stdin, case.cap)
        assert all(row.error is None for row in rows)
        last = rows[-1]
        assert last.halted
        assert last.state.output == 0
        assert last.output[0] == last.output[-1] == "0"
        assert len(last.output) == 6023
        assert int(Decimal(last.output[1:-1])) == 1 << 20000
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
    # A refused physical write leaves the $ token ready to retry.
    case = Case("$", "7 trailing")
    rows = model(case.source, case.stdin, case.cap)
    at = next(i for i in range(1, len(rows)) if rows[i].output != rows[i - 1].output)
    halt_at = next(i for i, row in enumerate(rows) if row.halted)
    prior, landed = rows[at - 1], rows[at]
    marker = "Fargo injected writer refusal"
    writes = []
    write = ScriptedIO._write
    accepting = False

    def refuse(port, value):
        assert type(value) is int
        assert value == 0
        writes.append(value)
        if accepting:
            return write(port, value)
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
                    assert_exact(
                        seen,
                        checker.esolangs.ExecutionResult(
                            prior.output,
                            landed.cursor,
                            landed.reads,
                            landed.past_end,
                            completion=None,
                            steps=at - 1 if route == 2 else None,
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
            assert_exact(actual, prior.state)
            accepting = True
            for _ in range(halt_at - at + 1):
                machine.step()
            accepting = False
            assert machine.halted
            counts["writer_routes"] += 1
        assert_exact(
            debugger.observation,
            checker.esolangs.ExecutionResult(
                rows[-1].output,
                landed.cursor,
                landed.reads,
                landed.past_end,
                completion=checker.REPORT,
                steps=halt_at,
            ),
        )
        assert (io.getvalue(), io.position(), io.progress(), io.reads, io.past_end) == (
            rows[-1].output,
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
            assert_exact(
                caught.observation,
                checker.esolangs.ExecutionResult(
                    prior.output,
                    landed.cursor,
                    landed.reads,
                    landed.past_end,
                    completion=None,
                    steps=at - 1,
                ),
            )
        else:
            raise AssertionError("public writer refusal swallowed")
        counts["writer_routes"] += 1
    assert len(writes) == 7
    assert all(type(value) is int and value == 0 for value in writes)
    return counts
