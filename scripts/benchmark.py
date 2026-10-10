"""Measure one generated artifact's size, time, steps, and actual answers."""

from __future__ import annotations

import argparse
import json
import signal
import statistics
import threading
import time
from dataclasses import fields, is_dataclass
from fractions import Fraction
from itertools import chain, compress
from operator import is_not
from typing import Any, cast

import esolangs
import esolangs.debugger as debugger_api
from esolangs._describe import LanguageInfo
from esolangs._validate import check_timeout
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import LANGUAGES
from esolangs.vm import VM, complete_vm, run_until_halt_or_cycle

_TEXT_TYPES = (str, bytes, bytearray)
_CONTAINER_TYPES = (tuple, list, frozenset, set)
_MEMO_TYPES = (tuple, frozenset, Fraction)


def _bits(row: int, inputs: int) -> list[int]:
    return [(row >> shift) & 1 for shift in range(inputs - 1, -1, -1)]


def _source_size(program: esolangs.Program) -> int:
    if isinstance(program, str):
        return len(program)
    return sum(len(row) for row in program.rows)


def _integer_bits(value: int) -> int:
    """Count magnitude bits (one for zero) and a sign bit for negatives."""
    return (value.bit_length() or 1) + (value < 0)


def state_bits(value: object, memo: dict[int, tuple[object, int]]) -> int:
    """Count a snapshot value's bits: integer widths, 8 per character.

    ``memo`` caches immutable containers by identity, so a persistent
    store's shared chunks are walked once a run, not once a step.
    """
    if value is None:
        return 0
    if isinstance(value, int):
        return (value.bit_length() or 1) + (value < 0)
    if isinstance(value, float):
        return 64
    if isinstance(value, _TEXT_TYPES):
        return 8 * len(value)
    hit = memo.get(id(value))
    if hit is not None and hit[0] is value:
        return hit[1]
    if isinstance(value, Fraction):
        total = state_bits(value.numerator, memo) + state_bits(value.denominator, memo)
    elif isinstance(value, dict):
        total = sum(state_bits(k, memo) + state_bits(v, memo) for k, v in value.items())
    elif isinstance(value, _CONTAINER_TYPES):
        items = value
        if (
            value
            and type(next(iter(value))) is tuple
            and set(map(type, value)) == {tuple}
        ):
            # Records of ints (a sparse tape's address-value pairs) count
            # as the flat run they hold; Streetcode re-sorts its every write.
            items = list(chain.from_iterable(value))
        try:
            # A flat run of ints (a tape, an array) counts in C: magnitude
            # bits, one more for each zero, one more for each negative --
            # _integer_bits per item, and bools agree.  SLOW ACV MAMMALIAN
            # rebuilds its 23 arrays every step, so identity memo cannot help.
            total = (
                sum(map(int.bit_length, items))
                + sum(map((0).__eq__, items))
                + sum(map((0).__gt__, items))
            )
        except TypeError:
            total = sum(state_bits(item, memo) for item in value)
    elif is_dataclass(value):
        total = sum(state_bits(getattr(value, f.name), memo) for f in fields(value))
    elif hasattr(value, "__dict__"):
        total = state_bits(vars(value), memo)
    elif slots := [
        name for cls in type(value).__mro__ for name in getattr(cls, "__slots__", ())
    ]:
        total = sum(state_bits(getattr(value, name, None), memo) for name in slots)
    else:
        raise TypeError(f"cannot count bits of {type(value).__name__}")
    if isinstance(value, _MEMO_TYPES):
        memo[id(value)] = (value, total)
    return total


class WrittenState:
    """Peak bits of the snapshot components a run writes.

    A top-level component never changed is read-only (code, an untouched
    grid) and excluded; one written counts whole at its peak, so a
    preallocated tape or a self-modified program is workspace.  Summing
    per-component peaks can only over-count.
    """

    def __init__(self, state: object) -> None:
        """Start from a run's first snapshot."""
        self._memo: dict[int, tuple[object, int]] = {}
        self._start = self._parts(state)
        self._peaks = [0] * len(self._start)
        self._written = [False] * len(self._start)
        self._last = list(self._start)
        #: Bits of each written part's last sample, for frozenset deltas.
        self._now: list[int | None] = [None] * len(self._start)

    @staticmethod
    def _parts(state: object) -> tuple[object, ...]:
        return state if isinstance(state, tuple) else (state,)

    def sample(self, state: object) -> None:
        """Record one snapshot."""
        parts = state if isinstance(state, tuple) else (state,)
        memo, peaks, written = self._memo, self._peaks, self._written
        start, previous, counts = self._start, self._last, self._now
        if len(parts) != len(start):
            raise ValueError("snapshot changed shape mid-run")
        for at, part in enumerate(parts):
            # Equal to the last sample, so equal bits: a rebuilt but
            # unchanged tape is compared in C, not walked in Python.
            last = previous[at]
            if part is last or part == last:
                continue
            previous[at] = part
            if not written[at]:
                written[at] = True
                peaks[at] = state_bits(start[at], memo)
            now = counts[at]
            if (
                now is not None
                and isinstance(part, frozenset)
                and isinstance(last, frozenset)
            ):
                # A frozenset counts as the sum of its items, so a painted
                # cell recounts the change, not A Painter Ant's whole grid.
                now += state_bits(part - last, memo)
                now -= state_bits(last - part, memo)
            elif (
                now is not None
                and isinstance(part, tuple)
                and isinstance(last, tuple)
                and len(part) == len(last)
                and part
                and isinstance(part[0], tuple)
            ):
                # A chunked store (Malbolge's memory, a persistent tape):
                # a tuple counts as the sum of its items, and an unwritten
                # chunk is the same object, so recount only the new ones.
                # A store rebuilt wholesale (Streetcode re-sorts its records)
                # moves most items, and one count in C beats that walk.
                changed = list(compress(range(len(part)), map(is_not, part, last)))
                if 8 * len(changed) < len(part):
                    for i in changed:
                        now += state_bits(part[i], memo)
                        now -= state_bits(last[i], memo)
                else:
                    now = state_bits(part, memo)
            else:
                now = state_bits(part, memo)
            counts[at] = now
            if now > peaks[at]:
                peaks[at] = now

    @property
    def bits(self) -> int:
        """Peak written bits so far."""
        return sum(self._peaks)


def _payload_profile(language: str, vm: VM) -> dict[str, int] | None:
    """Count logical data and control integers where the language splits them.

    Excludes Python overhead, static parser indexes and I/O state; what a
    machine's state holds is its ``LANGUAGE.payload``'s to say.
    """
    split = LANGUAGES[language].payload
    if split is None:
        return None
    data, control, pc, flags = split(vm.snapshot())
    data_widths = [_integer_bits(value) for value in data]
    control_widths = [_integer_bits(value) for value in control]
    data_bits = sum(data_widths)
    control_bits = sum(control_widths)
    pc_bits = _integer_bits(pc)
    return {
        "peak_control_stack_items": len(control),
        "peak_data_bits": data_bits,
        "peak_control_stack_bits": control_bits,
        "peak_integer_bits": max((*data_widths, *control_widths), default=0),
        "peak_pc_bits": pc_bits,
        "peak_machine_bits": data_bits + control_bits + pc_bits + flags,
    }


def _execute(
    language: str,
    program: esolangs.Program,
    table: str,
    row: int,
    cap: int,
    timeout: float | None,
    *,
    track_store: bool = False,
    facts: LanguageInfo | None = None,
) -> dict[str, Any]:
    if facts is None:
        facts = esolangs.describe(language)
    bits = _bits(row, len(table).bit_length() - 1)
    source: esolangs.Program
    if facts["parameterized"]:
        assert isinstance(program, str)
        source, stdin = esolangs.instantiate(language, program, bits), ""
    else:
        source, stdin = (
            program,
            esolangs.encode_inputs(language, bits, truth_table=table),
        )
    supported = facts["steppable_to_answer"]
    if track_store and facts["answer_mode"] == "termination":
        raise ValueError("store tracking requires a halting-answer language")
    result: dict[str, Any] = {
        "row": row,
        "expected_answer": table[row],
        "actual_answer": None,
        "matches": None,
        "commands": None,
        "stepping_status": "supported" if supported else "unsupported",
        "execution_status": "pending",
        "peak_memory_cells": None,
        "peak_stack_items": None,
        "peak_control_stack_items": None,
        "peak_data_bits": None,
        "peak_control_stack_bits": None,
        "peak_integer_bits": None,
        "peak_pc_bits": None,
        "peak_machine_bits": None,
        "peak_written_bits": None,
    }

    def drive(*_args: object) -> None:
        if not supported:
            output = esolangs.run(language, source, stdin=stdin)
            result["execution_status"] = "halted"
            result["actual_answer"] = esolangs.read_answer(language, output)
            return
        vm = debugger_api.make_vm(language, source, stdin=stdin)
        terminating = facts["answer_mode"] == "termination"
        if terminating:
            halted = run_until_halt_or_cycle(vm, limit=cap)
            if not halted:
                result["execution_status"] = "cycle"
                result["actual_answer"] = str(
                    list(facts["answer_encoding"]).index("diverges")
                )
                return
            # The detector unwraps the VM; replay a halt to retain the
            # baseline's wrapper-step count, excluding its post-halt dump.
            vm = debugger_api.make_vm(language, source, stdin=stdin)

        written = WrittenState(vm.snapshot()) if track_store else None

        def sample_store() -> None:
            if written is not None:
                written.sample(vm.snapshot())
                result["peak_written_bits"] = written.bits
                result["peak_memory_cells"] = max(
                    result["peak_memory_cells"] or 0, len(vm.memory)
                )
                result["peak_stack_items"] = max(
                    result["peak_stack_items"] or 0, len(vm.stack)
                )
                profile = _payload_profile(str(facts["name"]), vm)
                if profile is not None:
                    for key, value in profile.items():
                        result[key] = max(result[key] or 0, value)

        sample_store()
        steps = 0
        while not vm.halted and steps < cap:
            vm.step()
            steps += 1
            sample_store()
        result["commands"] = steps if vm.halted else None
        if not vm.halted:
            result["execution_status"] = "step_cap"
        elif terminating:
            result["execution_status"] = "halted"
            result["actual_answer"] = str(list(facts["answer_encoding"]).index("halts"))
        else:
            output = complete_vm(vm, max_steps=0)
            result["execution_status"] = "halted"
            result["actual_answer"] = esolangs.read_answer(language, output)

    try:
        # Cover VM construction too: a step cap cannot bound factoring.
        esolangs._run(drive, source, ScriptedIO(stdin), timeout)  # noqa: SLF001
    except esolangs.ExecutionTimeoutError:
        result["execution_status"] = "timeout"
    except TimeoutError:
        result["execution_status"] = "step_cap"
    if result["actual_answer"] is not None:
        result["matches"] = result["actual_answer"] == result["expected_answer"]
    return result


def _commands(
    language: str,
    program: esolangs.Program,
    table: str,
    row: int,
    cap: int,
) -> int | None:
    """Return steps to halt for the size screens, checking the same artifact."""
    result = _execute(language, program, table, row, cap, None)
    if result["matches"] is False:
        raise ValueError(f"{language} row {row}: wrong generated answer")
    return cast("int | None", result["commands"])


def measure(
    language: str,
    table: str,
    *,
    repeat: int,
    row: int,
    step_cap: int,
    all_rows: bool = False,
    sample_rows: tuple[int, ...] | None = None,
    timeout: float | None = 30.0,
    track_store: bool = False,
) -> dict[str, Any]:
    """Benchmark the last timed artifact; optionally check every input row."""
    if repeat < 1 or step_cap < 1:
        raise ValueError("repeat and step_cap must be positive")
    if not 0 <= row < len(table):
        raise ValueError("row must index the truth table")
    if sample_rows is not None and (
        not sample_rows
        or row not in sample_rows
        or any(not 0 <= at < len(table) for at in sample_rows)
    ):
        raise ValueError("sample rows must index the table and include row")
    check_timeout(timeout)
    if timeout is not None and not (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    ):
        raise esolangs.ArgumentError(
            "benchmark timeout needs a Unix main thread; pass timeout=None"
        )
    timings: list[int] = []
    program: esolangs.Program | None = None
    for _ in range(repeat):
        started = time.perf_counter_ns()
        program = esolangs.generate(language, table)
        _source_size(program)
        timings.append(time.perf_counter_ns() - started)
    assert program is not None
    facts = esolangs.describe(language)
    rows = range(len(table)) if all_rows else sample_rows or (row,)
    executions = [
        _execute(
            language,
            program,
            table,
            at,
            step_cap,
            timeout,
            track_store=track_store,
            facts=facts,
        )
        for at in rows
    ]
    selected = next(item for item in executions if item["row"] == row)
    return {
        "schema": 5,
        "track_store": track_store,
        "language": facts["name"],
        "truth_table": table,
        "inputs": len(table).bit_length() - 1,
        "source_kind": facts["source_kind"],
        "source_units": _source_size(program),
        "source_utf8_bits": 8 * len(program.encode("utf-8"))
        if isinstance(program, str)
        else None,
        "generation_ns_best": min(timings),
        "generation_ns_median": int(statistics.median(timings)),
        "step_cap": step_cap,
        "timeout": timeout,
        "all_rows": all_rows,
        "executions": executions,
        "worst_row_commands": (
            max(item["commands"] for item in executions)
            if all_rows and all(item["commands"] is not None for item in executions)
            else None
        ),
        **selected,
    }


def main(argv: list[str] | None = None) -> int:
    """Print JSON evidence; fail if any requested row is wrong or undecided."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("language")
    parser.add_argument("truth_table")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--row", type=int)
    parser.add_argument("--step-cap", type=int, default=2_000_000)
    bounds = parser.add_mutually_exclusive_group()
    bounds.add_argument("--timeout", type=float, default=30.0)
    bounds.add_argument(
        "--no-timeout", action="store_const", dest="timeout", const=None
    )
    parser.add_argument("--all-rows", action="store_true")
    parser.add_argument(
        "--track-store",
        action="store_true",
        help="sample stores; languages with a payload split report integers too",
    )
    args = parser.parse_args(argv)
    if args.repeat < 1 or args.step_cap < 1:
        parser.error("--repeat and --step-cap must be positive")
    row = len(args.truth_table) - 1 if args.row is None else args.row
    if not 0 <= row < len(args.truth_table):
        parser.error(f"--row must be in [0, {len(args.truth_table) - 1}]")
    result = measure(
        args.language,
        args.truth_table,
        repeat=args.repeat,
        row=row,
        step_cap=args.step_cap,
        all_rows=args.all_rows,
        timeout=args.timeout,
        track_store=args.track_store,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if all(item["matches"] is True for item in result["executions"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
