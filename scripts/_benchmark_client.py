"""Supervise reusable benchmark workers with portable phase deadlines."""

from __future__ import annotations

import builtins
import contextlib
import io
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, BinaryIO, cast

import esolangs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _verify_process import MAX_LOG_BYTES, spool
from _verify_process import EXCERPT_BYTES, stop_process_tree

MAX_RECORD_CHARS = 1024 * 1024


class Worker:
    """Reuse one interpreter across a sweep; kill the tree on any deadline."""

    def __init__(self, command: list[str] | None = None) -> None:
        self.command = command or [
            sys.executable,
            str(Path(__file__).with_name("_benchmark_worker.py")),
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
