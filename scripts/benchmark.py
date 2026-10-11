"""Measure one generated artifact's size, time, steps, and actual answers."""

from __future__ import annotations

import argparse
import builtins
import contextlib
import hashlib
import io
import json
import os
import platform
import queue
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import fields, is_dataclass
from fractions import Fraction
from itertools import chain, compress
from operator import is_not
from pathlib import Path
from typing import Any, BinaryIO, cast

import esolangs
import esolangs.debugger as debugger_api
from esolangs._describe import LanguageInfo
from esolangs._validate import check_timeout
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import LANGUAGES
from esolangs.vm import VM, complete_vm, run_until_halt_or_cycle

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.process import (
    EXCERPT_BYTES,
    MAX_LOG_BYTES,
    run_bounded,
    spool,
    stop_process_tree,
)

_TEXT_TYPES = (str, bytes, bytearray)
_CONTAINER_TYPES = (tuple, list, frozenset, set)
_MEMO_TYPES = (tuple, frozenset, Fraction)


def artifact_hash(program: esolangs.Program) -> str:
    """Hash UTF-8 text or dimensioned RGB rows without PNG encoder variation."""
    if isinstance(program, str):
        payload = b"text\0" + program.encode("utf-8")
    else:
        payload = b"rgb\0" + json.dumps(program.rows, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def source_identity(timeout: float = 60) -> dict[str, Any]:
    """Identify the checkout; refuse evidence without readable Git state."""
    root = Path(__file__).resolve().parents[1]

    check_timeout(timeout)
    deadline = time.monotonic() + timeout

    def git(*args: str) -> bytes:
        return cast(
            bytes,
            run_bounded(
                ["git", *args],
                cwd=root,
                capture_output=True,
                check=True,
                text=False,
                timeout=max(0, deadline - time.monotonic()),
            ).stdout,
        )

    untracked = hashlib.sha256()
    for name in sorted(
        git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    ):
        if name:
            untracked.update(name + b"\0")
            untracked.update(
                hashlib.sha256((root / os.fsdecode(name)).read_bytes()).digest()
            )
    return {
        "untracked_sha256": untracked.hexdigest(),
        "commit": git("rev-parse", "HEAD").decode().strip(),
        "dirty": bool(git("status", "--porcelain", "--untracked-files=normal")),
        "tracked_diff_sha256": hashlib.sha256(
            git("diff", "HEAD", "--binary")
        ).hexdigest(),
        "checkout": str(root),
    }


_WORKER: ContextVar[Worker | None] = ContextVar("benchmark_worker", default=None)

_EVIDENCE: ContextVar[dict[str, Any] | None] = ContextVar(
    "benchmark_evidence", default=None
)


@contextmanager
def evidence_session() -> Iterator[None]:
    """Check checkout state once around a sweep, before publishing its records."""
    identity = source_identity()
    token = _EVIDENCE.set(identity)
    worker = Worker()
    worker_token = _WORKER.set(worker)
    try:
        yield
        if source_identity() != identity:
            raise RuntimeError("checkout changed during benchmark")
    finally:
        worker.close()
        _WORKER.reset(worker_token)
        _EVIDENCE.reset(token)


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
    source_digest: str | None = None,
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
        "artifact_sha256": source_digest
        if source_digest is not None
        else artifact_hash(source),
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
    result = _execute(language, program, table, row, cap, None, source_digest="")
    if result["matches"] is False:
        raise ValueError(f"{language} row {row}: wrong generated answer")
    return cast("int | None", result["commands"])


def _measure(
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
    _progress: Callable[[str], None] | None = None,
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
    identity = _EVIDENCE.get() or source_identity()
    if _progress is not None:
        _progress("generation")
    timings: list[int] = []
    program: esolangs.Program | None = None
    for _ in range(repeat):
        started = time.perf_counter_ns()
        program = esolangs.generate(language, table)
        _source_size(program)
        timings.append(time.perf_counter_ns() - started)
    assert program is not None
    facts = esolangs.describe(language)
    digest = artifact_hash(program)
    rows = range(len(table)) if all_rows else sample_rows or (row,)
    executions = []
    for at in rows:
        if _progress is not None:
            _progress("execution")
        executions.append(
            _execute(
                language,
                program,
                table,
                at,
                step_cap,
                timeout,
                track_store=track_store,
                facts=facts,
                source_digest=None if facts["parameterized"] else digest,
            )
        )
    selected = next(item for item in executions if item["row"] == row)
    if _EVIDENCE.get() is None and source_identity() != identity:
        raise RuntimeError("checkout changed during benchmark")
    return {
        "schema": 6,
        "provenance": {
            **identity,
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "harness": 1,
            "generated_artifact_sha256": digest,
        },
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
    generation_timeout: float | None = 30.0,
) -> dict[str, Any]:
    """Bound generation and each execution row in a reusable supervised worker."""
    check_timeout(timeout)
    check_timeout(generation_timeout)
    identity = _EVIDENCE.get() or source_identity()
    worker = _WORKER.get() or Worker()
    arguments = {
        "language": language,
        "table": table,
        "repeat": repeat,
        "row": row,
        "step_cap": step_cap,
        "all_rows": all_rows,
        "sample_rows": sample_rows,
        "timeout": timeout,
        "track_store": track_store,
    }
    try:
        result = worker.measure(arguments, identity, generation_timeout)
        if _EVIDENCE.get() is None and source_identity() != identity:
            raise RuntimeError("checkout changed during benchmark")
        result["generation_timeout"] = generation_timeout
        return result
    finally:
        if _WORKER.get() is None:
            worker.close()


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
    parser.add_argument("--generation-timeout", type=float, default=30.0)
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
        generation_timeout=args.generation_timeout,
        track_store=args.track_store,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if all(item["matches"] is True for item in result["executions"]) else 1


MAX_RECORD_CHARS = 1024 * 1024


class Worker:
    """Reuse one interpreter across a sweep; kill the tree on any deadline."""

    def __init__(self, command: list[str] | None = None) -> None:
        """Spawn ``command``, or this module in ``--worker`` mode by default."""
        self.command = command or [
            sys.executable,
            str(Path(__file__).resolve().parent / "_lib" / "worker.py"),
        ]
        self.process: subprocess.Popen[str] | None = None
        self.messages: queue.Queue[str | None] = queue.Queue(maxsize=1)
        self.stopped = threading.Event()
        self.reader: threading.Thread | None = None
        self.writer: threading.Thread | None = None
        self.log_path: Path | None = None
        self.log_reader: threading.Thread | None = None
        self.log_overflow = threading.Event()

    def start(self) -> subprocess.Popen[str]:
        """Start the worker process if it is not already running."""
        if self.process is None:
            self.messages = queue.Queue(maxsize=1)
            self.stopped = threading.Event()
            directory = Path(__file__).resolve().parents[1] / "notes" / "benchmarks"
            directory.mkdir(parents=True, exist_ok=True)
            fd, filename = tempfile.mkstemp(
                prefix="worker-", suffix=".log", dir=directory
            )
            self.log_path = Path(filename)
            os.close(fd)
            self.log_overflow.clear()
            try:
                self.process = subprocess.Popen(
                    self.command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    start_new_session=os.name == "posix",
                    cwd=Path(__file__).resolve().parents[1],
                )
            except BaseException:
                self.log_path.unlink(missing_ok=True)
                raise
            process = self.process
            messages, stopped = self.messages, self.stopped

            def copy_log() -> None:
                assert process.stderr is not None
                assert self.log_path is not None

                def stop() -> None:
                    self.log_overflow.set()
                    stop_process_tree(process)

                spool(
                    cast(BinaryIO, cast("io.TextIOWrapper", process.stderr).buffer),
                    self.log_path,
                    MAX_LOG_BYTES,
                    stop,
                )

            self.log_reader = threading.Thread(target=copy_log, daemon=True)
            self.log_reader.start()

            def read() -> None:
                assert process.stdout is not None
                while not stopped.is_set():
                    line = process.stdout.readline(MAX_RECORD_CHARS + 1) or None
                    oversized = line is not None and len(line) > MAX_RECORD_CHARS
                    if oversized:
                        line = json.dumps(
                            {
                                "error": {
                                    "type": "RuntimeError",
                                    "message": "benchmark worker record exceeds limit",
                                }
                            }
                        )
                    while not stopped.is_set():
                        try:
                            messages.put(line, timeout=0.05)
                            break
                        except queue.Full:
                            pass
                    if line is None or oversized:
                        break

            self.reader = threading.Thread(target=read, daemon=True)
            self.reader.start()
        return self.process

    def close(self, *, check_log: bool = True) -> None:
        """Stop the worker tree and surface a truncated diagnostic log."""
        if self.process is not None:
            self.stopped.set()
            stop_process_tree(self.process)
            if self.reader is not None:
                self.reader.join(5)
            if self.writer is not None:
                self.writer.join(5)
            if self.log_reader is not None:
                self.log_reader.join(5)
            for stream in (
                self.process.stdin,
                self.process.stdout,
                self.process.stderr,
            ):
                # Closing a pipe to a reaped worker flushes and raises
                # BrokenPipeError; cleanup must not mask the deadline that
                # triggered it (the worker is killed before this runs).
                if stream is not None:
                    with contextlib.suppress(OSError):
                        stream.close()
            self.process = None
            if check_log and self.log_overflow.is_set():
                raise RuntimeError("benchmark diagnostic byte limit exceeded")

    def measure(
        self,
        arguments: dict[str, Any],
        identity: dict[str, Any],
        generation_timeout: float | None,
        *,
        total_timeout: float | None = None,
    ) -> dict[str, Any]:
        """Measure one request through the worker, killing its tree on a deadline."""
        process = self.start()
        phase, limit = "generation", generation_timeout
        deadline = None if limit is None else time.monotonic() + limit
        total_deadline = (
            None if total_timeout is None else time.monotonic() + total_timeout
        )
        generated = False
        executed = 0
        expected = (
            len(arguments.get("table", ""))
            if arguments.get("all_rows")
            else len(arguments.get("sample_rows") or (0,))
        )
        try:
            messages, stopped = self.messages, self.stopped

            def send() -> None:
                assert process.stdin is not None
                try:
                    process.stdin.write(
                        json.dumps({"arguments": arguments, "identity": identity})
                        + "\n"
                    )
                    process.stdin.flush()
                except OSError as error:
                    failure = json.dumps(
                        {"error": {"type": type(error).__name__, "message": str(error)}}
                    )
                    while not stopped.is_set():
                        try:
                            messages.put(failure, timeout=0.05)
                            break
                        except queue.Full:
                            pass

            self.writer = threading.Thread(target=send, daemon=True)
            self.writer.start()
            while True:
                remaining = (
                    None if deadline is None else max(0.0, deadline - time.monotonic())
                )
                if total_deadline is not None:
                    total_remaining = max(0.0, total_deadline - time.monotonic())
                    if total_remaining == 0:
                        raise esolangs.ExecutionTimeoutError(
                            "benchmark total work deadline exceeded"
                        )
                    remaining = (
                        total_remaining
                        if remaining is None
                        else min(remaining, total_remaining)
                    )
                try:
                    line = self.messages.get(timeout=remaining)
                except queue.Empty:
                    if (
                        total_deadline is not None
                        and time.monotonic() >= total_deadline
                    ):
                        raise esolangs.ExecutionTimeoutError(
                            "benchmark total work deadline exceeded"
                        ) from None
                    raise esolangs.ExecutionTimeoutError(
                        f"benchmark {phase} deadline exceeded ({limit:g}s)"
                    ) from None
                if self.log_overflow.is_set():
                    raise RuntimeError("benchmark diagnostic byte limit exceeded")
                if line is None:
                    raise RuntimeError("benchmark worker exited without evidence")
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise RuntimeError("invalid benchmark worker record")
                if "phase" in message:
                    next_phase = message["phase"]
                    if (
                        next_phase == "generation"
                        and not generated
                        and set(message) == {"phase"}
                    ):
                        generated = True
                    elif (
                        next_phase == "execution"
                        and generated
                        and executed < expected
                        and type(message.get("index")) is int
                        and message["index"] == executed
                        and set(message) == {"phase", "index"}
                    ):
                        phase = next_phase
                        executed += 1
                        limit = arguments["timeout"]
                        deadline = None if limit is None else time.monotonic() + limit
                    else:
                        raise RuntimeError("invalid benchmark worker phase transition")
                elif "result" in message:
                    if (
                        not generated
                        or executed != expected
                        or set(message) != {"result"}
                        or not isinstance(message["result"], dict)
                    ):
                        raise RuntimeError(
                            "premature or invalid benchmark worker result"
                        )
                    return dict(message["result"])
                elif "error" in message:
                    error = message["error"]
                    if (
                        set(message) != {"error"}
                        or not isinstance(error, dict)
                        or set(error) != {"type", "message"}
                        or not all(isinstance(value, str) for value in error.values())
                    ):
                        raise RuntimeError("invalid benchmark worker error")
                    cls = getattr(
                        esolangs,
                        error["type"],
                        getattr(builtins, error["type"], RuntimeError),
                    )
                    if not isinstance(cls, type) or not issubclass(cls, Exception):
                        cls = RuntimeError
                    raise cls(error["message"])
                else:
                    raise RuntimeError("invalid benchmark worker record")
        except BaseException as error:
            self.close(check_log=False)
            if isinstance(error, Exception) and self.log_overflow.is_set():
                error = RuntimeError("benchmark diagnostic byte limit exceeded")
            if isinstance(error, Exception) and self.log_path is not None:
                with self.log_path.open("rb") as log:
                    log.seek(max(0, self.log_path.stat().st_size - EXCERPT_BYTES))
                    tail = log.read(EXCERPT_BYTES).decode("utf-8", errors="replace")
                error.add_note(f"[log] {self.log_path}\n{tail}")
            raise error


if __name__ == "__main__":
    raise SystemExit(main())
