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
    _settings_of,
    _split_positional,
    _timeout_of,
)
from esolangs.cli.hints import (
    _TIMEOUT_EXIT,
    _as_argument,
    _exit_code,
    _stdin_hint,
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
from esolangs.operations.execution import default_total
from esolangs.registry import LANGUAGES, resolve, template_char
from esolangs.runtime._execution import check_seed_for
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
    # A cap selects the worker, as run(max_output=...) does; both flags
    # exited 2 with "requires --isolated".
    isolated = bool({"--isolated", "--max-output", "--max-memory"} & {*flags, *options})
    worker_total = (
        default_total(total, timeout)
        if isolated or timeout is not None or preparation is not None
        else total
    )
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
    max_output = None
    if "--max-output" in options:
        max_output = _integer(
            options["--max-output"], "--max-output", kind="a non-negative integer"
        )
        _nonnegative(max_output, "--max-output", options["--max-output"])
    max_memory = None
    if "--max-memory" in options:
        max_memory = _integer(
            options["--max-memory"], "--max-memory", kind="a positive integer"
        )
        if max_memory < 1:
            _fail(
                "--max-memory must be a positive integer, got "
                f"{format_integer(max_memory)}"
            )
        try:
            check_memory(max_memory, isolated=isolated)
        except ArgumentError as exc:  # "max_memory is supported only on Linux"
            _fail(str(exc).replace("max_memory", "--max-memory"))
    rest = _split_positional(rest, set(), value_options | {"--set", "--isolated"})
    seed = _seed_of(options)
    scale = _scale_of(options)
    _check_count("run", rest, 2)
    language, path = rest
    settings = _settings_of(options, set_pairs, language=language)
    # Resolved *before* stdin is read.  It was after, so
    # `esolangs run NotALang prog.txt` with stdin held open blocked forever
    # without ever saying the language was unknown -- the one thing it could
    # have answered without reading a byte.
    with _errors():
        dialect_options(language, settings)
        declaration = LANGUAGES[resolve(language)]
        # Before stdin too: held open, `run --seed 1 brainfuck` hung here.
        check_seed_for(declaration.name, seed)
        check_scale_for(declaration.name, scale)
    # No Boolean-answer notes here: run takes any program, and the
    # termination contract (halt 0, diverge 1) is a generated program's,
    # stated by describe and read-answer.
    program = _read_program(
        path,
        _remaining(acquisition, monotonic() - started, flag),
        language=declaration.name,
        timeout_flag=flag,
    )
    stdin = _read_stdin(
        _remaining(acquisition, monotonic() - started, flag),
        _stdin_hint(declaration),
        timeout_flag=flag,
    )
    _remaining(acquisition, monotonic() - started, flag)
    try:
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
                limits=ExecutionLimits(
                    preparation_timeout=preparation,
                    execution_timeout=timeout,
                    total_timeout=total,
                    max_steps=max_steps,
                    max_output=max_output,
                    max_memory=max_memory,
                ),
                seed=seed,
                scale=scale,
                isolated=isolated,
                settings=settings,
            ).output
    except TemplateError as exc:
        _fail(_template_hint(exc, language))
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
    empty = isinstance(program.source, str) and not program.source.strip()
    slot = template_char(declaration.id)
    if slot is not None and isinstance(program.source, str) and slot in program.source:
        _note(
            f"note: {path} contains {slot!r}, which marks an unfilled input slot "
            "in generated templates. To fill one, use: esolangs generate --bits "
            f"<bits> {_as_argument(language)} <table>"
        )
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
