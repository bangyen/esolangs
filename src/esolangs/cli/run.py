"""``esolangs run``: one program through its interpreter."""

from __future__ import annotations

import sys
from contextlib import nullcontext
from time import monotonic

from esolangs import ExecutionLimits, run
from esolangs.cli.args import (
    _VALUE_OPTIONS,
    _check_count,
    _errors,
    _fail,
    _integer,
    _nonnegative,
    _pop_flags,
    _pop_options,
    _pop_set_pairs,
    _scale_of,
    _seed_of,
    _settings_arguments,
    _settings_of,
    _split_positional,
    _timeout_of,
)
from esolangs.cli.hints import (
    _TIMEOUT_EXIT,
    _exit_code,
    _template_hint,
    _timeout_text,
)
from esolangs.cli.io import (
    _emit_partial,
    _note,
    _read_program,
    _read_stdin,
    _unbounded_notice,
    _write_output,
)
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionBudgetError,
    TemplateError,
)
from esolangs.operations.execution import _execution_route, default_total
from esolangs.registry import get_catalog
from esolangs.runtime._execution import check_seed_for, check_worker_runtime
from esolangs.runtime._files import _source_directory
from esolangs.runtime._isolated import _acquisition_started_at, check_memory
from esolangs.runtime._source import check_scale_for
from esolangs.runtime.memory import format_integer
from esolangs.settings import dialect_options


def _remaining(timeout: float | None, elapsed: float, flag: str) -> float | None:
    """Charge acquisition time to the original deadline."""
    if timeout is None:
        return None
    remaining = timeout - elapsed
    if remaining <= 0:
        _fail(f"{flag} expired while loading the program or stdin", _TIMEOUT_EXIT)
    return remaining


def _run(rest: list[str]) -> None:
    """Run a program through its interpreter and write its output."""
    started = monotonic()
    rest, set_pairs = _pop_set_pairs(rest)
    value_options = _VALUE_OPTIONS["run"] - {"--set"}
    rest, options = _pop_options(rest, value_options)
    # The value is checked here, before the positionals are counted.  It ran
    # after, so `run --execution-timeout brainfuck prog.txt` -- a forgotten number --
    # swallowed the language as the timeout's value and then reported
    # "missing <program-file>", sending the reader to look at the one
    # argument that was not the problem.
    timeout = _timeout_of(options)
    total = _timeout_of(options, option="--total-timeout")
    preparation = _timeout_of(options, option="--preparation-timeout")
    max_steps = None
    if "--max-steps" in options:
        max_steps = _integer(
            options["--max-steps"], "--max-steps", kind="a non-negative integer"
        )
        _nonnegative(max_steps, "--max-steps", options["--max-steps"])
    rest, flags = _pop_flags(rest, {"--isolated"})
    isolated = "--isolated" in flags
    max_output = None
    if "--max-output" in options:
        max_output = _integer(
            options["--max-output"], "--max-output", kind="a non-negative integer"
        )
        _nonnegative(max_output, "--max-output", options["--max-output"])
    max_memory = None
    if "--max-memory" in options:
        max_memory = _integer(
            options["--max-memory"],
            "--max-memory",
            kind="a positive integer",
        )
        if max_memory < 1:
            _fail(
                "--max-memory must be a positive integer, got "
                f"{format_integer(max_memory)}"
            )
        try:
            check_memory(max_memory, isolated=True)
        except ArgumentError as exc:  # "max_memory is supported only on Linux"
            _fail(str(exc).replace("max_memory", "--max-memory"))
    limits = ExecutionLimits(
        preparation_timeout=preparation,
        execution_timeout=timeout,
        total_timeout=total,
        max_steps=max_steps,
        max_output=max_output,
        max_memory=max_memory,
    )
    worker, _ = _execution_route(limits, isolated=isolated, prepared=False)
    worker_total = default_total(total, timeout) if worker else None
    # File and stdin share the tightest acquisition budget. Execution gets
    # its own execution_timeout after the worker has prepared the program.
    acquisition, flag = min(
        (
            (bound, flag)
            for bound, flag in (
                (worker_total, "--total-timeout"),
                (preparation, "--preparation-timeout"),
                (timeout, "--execution-timeout"),
            )
            if bound is not None
        ),
        default=(None, ""),
        key=lambda pair: pair[0],
    )
    rest = _split_positional(rest, set(), value_options | {"--set", "--isolated"})
    seed = _seed_of(options)
    scale = _scale_of(options)
    settings_arguments = _settings_arguments(options, set_pairs)
    catalog = get_catalog()
    _check_count("run", rest, 2, catalog=catalog)
    language, path = rest
    directory = _source_directory(path) if path else None
    settings = _settings_of(settings_arguments, language=language, catalog=catalog)
    # Resolved *before* stdin is read.  It was after, so
    # `esolangs run NotALang prog.txt` with stdin held open blocked forever
    # without ever saying the language was unknown -- the one thing it could
    # have answered without reading a byte.
    with _errors():
        dialect_options(language, settings, catalog=catalog)
        declaration = catalog.languages[catalog.resolve(language)]
        # Before stdin too: held open, `run --seed 1 brainfuck` hung here.
        check_seed_for(declaration.name, seed, catalog=catalog)
        check_scale_for(declaration.name, scale, catalog=catalog)
        if worker:
            check_worker_runtime(declaration.name, catalog)
    # No Boolean-answer notes here: run takes any program, and the
    # termination contract (halt 0, diverge 1) is a generated program's,
    # stated by describe and read-answer.
    program = _read_program(
        path,
        _remaining(acquisition, monotonic() - started, flag),
        language=declaration.name,
        timeout_flag=flag,
        directory=directory,
        settings=settings,
        catalog=catalog,
    )
    try:
        if scale is None and program.scale is not None:
            check_scale_for(declaration.name, program.scale, catalog=catalog)
        stdin = ""
        if declaration.runtime.reads_stdin:
            stdin = _read_stdin(
                _remaining(acquisition, monotonic() - started, flag),
                "; send the input this program needs, or close stdin",
                timeout_flag=flag,
            )
        _remaining(acquisition, monotonic() - started, flag)
        with (
            _unbounded_notice("run")
            if acquisition is None and max_steps is None
            else nullcontext(),
            _acquisition_started_at(started),
        ):
            output = run(
                language,
                program,
                stdin=stdin,
                limits=limits,
                seed=seed,
                scale=scale,
                isolated=isolated,
                settings=settings,
                catalog=catalog,
            ).output
    except TemplateError as exc:
        _fail(_template_hint(exc, language, catalog=catalog))
    except ExecutionBudgetError as exc:
        # Distinct from a program error's 1, following timeout(1), so a
        # script can tell "ran out of time" from "the program broke".  Those
        # shared exit 1, which made the termination languages'
        # answer indistinguishable from a crash.
        _emit_partial(exc)
        _fail(_timeout_text(exc), _TIMEOUT_EXIT)
    except EsolangError as exc:
        # A usage error (an unknown language) is still 2; anything the
        # program itself did is the program's failure, and exits 1.
        _emit_partial(exc)
        _fail(exc, _exit_code(exc))
    _write_output(output)
    # Piped output stays byte-exact -- it gets compared and diffed -- but a
    # result with no trailing newline runs into the next shell prompt.
    if output and not output.endswith("\n") and sys.stdout.isatty():
        _write_output("\n")
    empty = isinstance(program.source, str) and not program.source
    if empty:
        # Legal, and almost never what was meant: an empty file is what you
        # get from a redirect that failed or a generate that was never run.
        # Said on stderr, so a pipeline still receives the empty output.
        _note(f"note: {path} is empty, so there was no program to run")
    # A program that printed nothing is a legal program, and also what you
    # get from an empty file or the wrong path.  Say so on a terminal, where
    # the alternative is a blank line and no way to tell the two apart; a
    # pipe still receives exactly the empty output.
    if not output and sys.stdout.isatty():
        _note(
            f"{language}: the program ran and printed nothing"
            f"{' (the file is empty)' if empty else ''}"
        )
