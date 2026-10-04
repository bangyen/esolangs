"""Generate one answer, or evaluate a supplied program on every row."""

from __future__ import annotations

import signal
from time import monotonic

from esolangs import (
    Raster,
    describe,
    encode_inputs,
    evaluate,
    generate,
    instantiate,
    read_answer,
    run,
)
from esolangs._answers import _validate_shape_for_evaluate
from esolangs._evaluate import (
    _DEFAULT_MAX_ROWS,
    _evaluation_rows,
    _prepare,
    _remaining,
)
from esolangs._program import Program
from esolangs._validate import check_whole
from esolangs.cli_args import (
    _check_count,
    _fail,
    _integer,
    _pop_options,
    _pop_portable,
    _settings_of,
    _split_positional,
    _table_of,
    _timeout_of,
)
from esolangs.cli_hints import _diverging_answer, _exit_code
from esolangs.cli_io import _read_program
from esolangs.exceptions import EsolangError
from esolangs.settings import dialect_options


def _answer(rest: list[str]) -> None:
    """Generate, feed one row's bits, run, and print the answer bit."""
    rest, options = _pop_options(rest, {"--timeout", "--settings"})
    timeout = _timeout_of(options)
    rest = _split_positional(rest, set(), {"--timeout", "--settings"})
    _check_count("answer", rest, 3)
    language, table, bits = rest
    settings = _settings_of(options)
    if set(bits) - {"0", "1"} or not bits:
        _fail(f"bits must be a string of 0s and 1s, got {bits!r}")
    try:
        facts = describe(language)
        name = str(facts["name"])
        row = [int(bit) for bit in bits]
        program = generate(name, table, settings=settings)
        source: Program
        if facts["parameterized"]:
            if isinstance(program, Raster):  # pragma: no cover - inconsistent metadata
                raise TypeError("a raster generator cannot be parameterized")
            source, stdin = (
                instantiate(name, program, row, truth_table=table, settings=settings),
                "",
            )
        else:
            source, stdin = program, encode_inputs(name, row, table)
        if facts["answer_mode"] == "termination":
            if not isinstance(source, str):  # pragma: no cover - inconsistent metadata
                raise TypeError("a raster language cannot answer by termination")
            # A bound is the answer here rather than a safeguard, so one is
            # supplied: this command exists to be a one-liner, and making a
            # reader discover that the termination-answer languages need a
            # flag would defeat that.
            print(
                _diverging_answer(
                    name, source, stdin, timeout or 5.0, facts, settings=settings
                )
            )
            return
        print(read_answer(name, run(name, source, stdin, timeout, settings=settings)))
    except EsolangError as exc:
        # No ``TemplateError`` clause: this command generates the template
        # and fills it in the same breath, so it never hands an unfilled one
        # on.
        _fail(exc, _exit_code(exc))


def _evaluate(rest: list[str]) -> None:
    """Print a supplied program's table, optionally checking the expected one."""
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
            "--portable",
        },
    )
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
    language, path = rest
    settings = _settings_of(options)
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
