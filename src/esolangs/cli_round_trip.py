"""Generate one answer, or evaluate a supplied program on every row."""

from __future__ import annotations

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
from esolangs._program import Program
from esolangs.cli_args import (
    _check_count,
    _fail,
    _integer,
    _pop_options,
    _split_positional,
    _table_of,
    _timeout_of,
)
from esolangs.cli_hints import _diverging_answer, _exit_code
from esolangs.cli_io import _read_program
from esolangs.exceptions import EsolangError


def _answer(rest: list[str]) -> None:
    """Generate, feed one row's bits, run, and print the answer bit."""
    rest, options = _pop_options(rest, {"--timeout"})
    timeout = _timeout_of(options)
    rest = _split_positional(rest, set(), {"--timeout"})
    _check_count("answer", rest, 3)
    language, table, bits = rest
    if set(bits) - {"0", "1"} or not bits:
        _fail(f"bits must be a string of 0s and 1s, got {bits!r}")
    try:
        facts = describe(language)
        name = str(facts["name"])
        row = [int(bit) for bit in bits]
        program = generate(name, table)
        source: Program
        if facts["parameterized"]:
            if isinstance(program, Raster):  # pragma: no cover - inconsistent metadata
                raise TypeError("a raster generator cannot be parameterized")
            source, stdin = instantiate(name, program, row, truth_table=table), ""
        else:
            source, stdin = program, encode_inputs(name, row, table)
        if facts["answer_mode"] == "termination":
            if not isinstance(source, str):  # pragma: no cover - inconsistent metadata
                raise TypeError("a raster language cannot answer by termination")
            # A bound is the answer here rather than a safeguard, so one is
            # supplied: this command exists to be a one-liner, and making a
            # reader discover that the termination-answer languages need a
            # flag would defeat that.
            print(_diverging_answer(name, source, stdin, timeout or 5.0, facts))
            return
        print(read_answer(name, run(name, source, stdin, timeout)))
    except EsolangError as exc:
        # No ``TemplateError`` clause: this command generates the template
        # and fills it in the same breath, so it never hands an unfilled one
        # on.
        _fail(str(exc), _exit_code(exc))


def _evaluate(rest: list[str]) -> None:
    """Print a supplied program's table, optionally checking the expected one."""
    rest, options = _pop_options(rest, {"--timeout", "--inputs", "--table"})
    timeout = _timeout_of(options)
    rest = _split_positional(rest, set(), {"--timeout", "--inputs", "--table"})
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
    language, path = rest
    program = _read_program(path, timeout, language=language)
    try:
        if timeout is None:
            computed = evaluate(language, program, inputs=inputs)
        else:
            computed = evaluate(language, program, timeout, inputs=inputs)
    except EsolangError as exc:
        _fail(str(exc), _exit_code(exc))
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
