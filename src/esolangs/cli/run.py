"""``esolangs run``: one program through its interpreter."""

from __future__ import annotations

import sys
import warnings
from contextlib import nullcontext

from esolangs import describe, run
from esolangs.cli.args import (
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
    _exit_code,
    _stdin_hint,
    _template_hint,
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
    ExecutionTimeoutError,
    TemplateError,
)
from esolangs.runtime._execution import check_seed_for
from esolangs.runtime._isolated import check_memory
from esolangs.settings import dialect_options


def _run(rest: list[str]) -> None:
    """Run a program through its interpreter and write its output."""
    rest, set_pairs = _pop_set_pairs(rest)
    value_options = {
        "--timeout",
        "--seed",
        "--scale",
        "--max-output",
        "--max-memory",
        "--settings",
    }
    rest, options = _pop_options(rest, value_options)
    # The value is checked here, before the positionals are counted.  It ran
    # after, so `run --timeout brainfuck prog.txt` -- a forgotten number --
    # swallowed the language as the timeout's value and then reported
    # "missing <program-file>", sending the reader to look at the one
    # argument that was not the problem.
    timeout = _timeout_of(options)
    rest, flags = _pop_flags(rest, {"--isolated"})
    isolated = "--isolated" in flags
    if isolated and timeout is None:
        timeout = 30.0
    max_output = None
    if "--max-output" in options:
        if not isolated:
            _fail("--max-output requires --isolated")
        max_output = _integer(
            options["--max-output"], "--max-output", kind="a non-negative integer"
        )
        _nonnegative(max_output, "--max-output", options["--max-output"])
    max_memory = None
    if "--max-memory" in options:
        # Checked by flag name, as --max-output is; the API's message said
        # "max_memory requires isolated=True".
        if not isolated:
            _fail("--max-memory requires --isolated")
        max_memory = _integer(
            options["--max-memory"], "--max-memory", kind="a positive integer"
        )
        if max_memory < 1:
            _fail(f"--max-memory must be a positive integer, got {max_memory}")
        try:
            check_memory(max_memory, isolated=isolated)
        except ArgumentError as exc:  # "max_memory is supported only on Linux"
            _fail(str(exc).replace("max_memory", "--max-memory"))
    rest = _split_positional(rest, set(), value_options | {"--set", "--isolated"})
    seed = _seed_of(options)
    scale = _scale_of(options)
    if flags.count("--isolated") > 1:
        _fail("--isolated given more than once")
    _check_count("run", rest, 2)
    language, path = rest
    settings = _settings_of(options, set_pairs, language=language)
    # Resolved *before* stdin is read.  It was after, so
    # `esolangs run NotALang prog.txt` with stdin held open blocked forever
    # without ever saying the language was unknown -- the one thing it could
    # have answered without reading a byte.
    with _errors():
        dialect_options(language, settings)
        facts = describe(language)
        # Before stdin too: held open, `run --seed 1 brainfuck` hung here.
        check_seed_for(facts["name"], seed)
    # No Boolean-answer notes here: run takes any program, and the
    # termination contract (halt 0, diverge 1) is a generated program's,
    # stated by describe and read-answer.
    program = _read_program(path, timeout, language=language)
    stdin = _read_stdin(timeout, _stdin_hint(facts))
    try:
        with (
            _unbounded_notice("run") if timeout is None else nullcontext(),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            output = run(
                language,
                program,
                stdin=stdin,
                timeout=timeout,
                seed=seed,
                scale=scale,
                isolated=isolated,
                max_output=max_output,
                max_memory=max_memory,
                settings=settings,
            )
        for entry in caught:
            _note(str(entry.message))
    except TemplateError as exc:
        _fail(_template_hint(exc, language))
    except ExecutionTimeoutError as exc:
        # Distinct from a program error's 1, following timeout(1), so a
        # script can tell "ran out of time" from "the program broke".  Those
        # shared exit 1, which made the termination languages'
        # answer indistinguishable from a crash.
        _emit_partial(exc)
        _fail(exc, _TIMEOUT_EXIT)
    except EsolangError as exc:
        # A usage error (an unknown language) is still 2; anything the
        # program itself did is the program's failure, and exits 1.
        _emit_partial(exc)
        _fail(exc, _exit_code(exc))
    _write_output(output)
    # Piped output stays byte-exact -- it gets compared and diffed -- but a
    # result with no trailing newline runs into the next shell prompt.
    if output and not output.endswith("\n") and sys.stdout.isatty():
        sys.stdout.write("\n")
    empty = isinstance(program, str) and not program.strip()
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
        sys.stderr.write(
            f"{language}: the program ran and printed nothing"
            f"{' (the file is empty)' if empty else ''}\n"
        )
