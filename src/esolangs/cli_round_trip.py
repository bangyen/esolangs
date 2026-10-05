"""Generate one answer, or evaluate a supplied program on every row."""

from __future__ import annotations

import signal
from time import monotonic

from esolangs import (
    describe,
    evaluate,
)
from esolangs._answers import _validate_shape_for_evaluate
from esolangs._evaluate import (
    _DEFAULT_MAX_ROWS,
    _evaluation_rows,
    _prepare,
    _remaining,
)
from esolangs._validate import check_whole
from esolangs.cli_args import (
    _check_count,
    _errors,
    _fail,
    _integer,
    _pop_options,
    _pop_portable,
    _pop_set_pairs,
    _settings_of,
    _split_positional,
    _table_of,
    _timeout_of,
)
from esolangs.cli_hints import _exit_code
from esolangs.cli_io import _portable_language, _read_program
from esolangs.exceptions import EsolangError
from esolangs.settings import dialect_options


def _evaluate(rest: list[str]) -> None:
    """Print a supplied program's table, optionally checking the expected one."""
    rest, set_pairs = _pop_set_pairs(rest)
    rest, options = _pop_options(
        rest,
        {
            "--timeout",
            "--inputs",
            "--table",
            "--max-rows",
            "--max-output",
            "--max-memory",
            "--total-timeout",
            "--settings",
        },
    )
    rest, portable = _pop_portable(rest)
    timeout = _timeout_of(options)
    rest = _split_positional(
        rest,
        set(),
        {
            "--timeout",
            "--inputs",
            "--table",
            "--max-rows",
            "--max-output",
            "--max-memory",
            "--total-timeout",
            "--settings",
            "--set",
            "--portable",
        },
    )
    if not (portable and len(rest) == 1):
        _check_count("evaluate", rest, 2)
    table = _table_of(options)
    if "--inputs" in options and table is not None:
        _fail("--inputs and --table are mutually exclusive")
    if table is not None:
        inputs = _validate_shape_for_evaluate(table)
    elif "--inputs" in options:
        inputs = _integer(options["--inputs"], "--inputs", show_value=False)
    else:
        _fail("evaluate requires --inputs N or --table TABLE")
    max_rows = (
        _integer(options["--max-rows"], "--max-rows")
        if "--max-rows" in options
        else _DEFAULT_MAX_ROWS
    )
    max_output = (
        _integer(options["--max-output"], "--max-output")
        if "--max-output" in options
        else None
    )
    total_timeout = (
        _timeout_of(options, option="--total-timeout")
        if "--total-timeout" in options
        else None
    )
    if portable and len(rest) == 1:
        path = rest[0]
        with _errors():
            language = _portable_language(path, timeout)
    else:
        language, path = rest
    settings = _settings_of(options, set_pairs, language=language)
    max_memory = (
        _integer(options["--max-memory"], "--max-memory")
        if "--max-memory" in options
        else None
    )
    isolated = (
        max_output is not None
        or max_memory is not None
        or not hasattr(signal, "SIGALRM")
    )
    deadline = None if total_timeout is None else monotonic() + total_timeout
    try:
        from esolangs._isolated import check_memory

        check_memory(max_memory, isolated=isolated)
        if not portable:
            dialect_options(language, settings)
        else:
            describe(language)
        _evaluation_rows(inputs, max_rows)
        if max_output is not None:
            check_whole(max_output, "max_output")
        program = _prepare(
            lambda: _read_program(
                path, timeout, language=language, portable=portable, settings=settings
            ),
            deadline,
            isolated=isolated,
        )
        total_timeout = _remaining(deadline, None)
        if timeout is None:
            computed = evaluate(
                language,
                program,
                inputs=inputs,
                max_rows=max_rows,
                max_output=max_output,
                max_memory=max_memory,
                total_timeout=total_timeout,
                isolated=isolated,
                settings=settings,
            )
        else:
            computed = evaluate(
                language,
                program,
                timeout,
                inputs=inputs,
                max_rows=max_rows,
                max_output=max_output,
                max_memory=max_memory,
                total_timeout=total_timeout,
                isolated=isolated,
                settings=settings,
            )
    except EsolangError as exc:
        _fail(exc, _exit_code(exc))
    if table is not None and computed != table:
        differing = [
            i for i, (a, b) in enumerate(zip(computed, table, strict=True)) if a != b
        ]
        _fail(
            f"computed {computed}, wanted {table}\n"
            f"{len(differing)} row(s) disagree: {', '.join(map(str, differing))}",
            1,
        )
    print(computed)
