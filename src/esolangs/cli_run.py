"""``esolangs run``: one program through its interpreter."""

from __future__ import annotations

import sys
import warnings

from esolangs import describe, run
from esolangs.cli_args import (
    _check_count,
    _errors,
    _fail,
    _integer,
    _nonnegative,
    _pop_flags,
    _pop_options,
    _pop_portable,
    _pop_set_pairs,
    _scale_of,
    _seed_of,
    _settings_of,
    _split_positional,
    _timeout_of,
)
from esolangs.cli_hints import (
    _TIMEOUT_EXIT,
    _exit_code,
    _stdin_hint,
    _template_hint,
)
from esolangs.cli_io import (
    _emit_partial,
    _note,
    _null_context,
    _portable_language,
    _read_program,
    _read_stdin,
    _UnboundedNotice,
    _write_output,
)
from esolangs.exceptions import EsolangError, ExecutionTimeoutError, TemplateError
from esolangs.settings import dialect_options


def _run(rest: list[str]) -> None:
    """Run a program through its interpreter and write its output."""
    rest, set_pairs = _pop_set_pairs(rest)
    rest, options = _pop_options(
        rest,
        {
            "--timeout",
            "--seed",
            "--scale",
            "--max-output",
            "--max-memory",
            "--settings",
        },
    )
    # The value is checked here, before the positionals are counted.  It ran
    # after, so `run --timeout brainfuck prog.txt` -- a forgotten number --
    # swallowed the language as the timeout's value and then reported
    # "missing <program-file>", sending the reader to look at the one
    # argument that was not the problem.
    timeout = _timeout_of(options)
    rest, portable = _pop_portable(rest)
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
        max_memory = _integer(options["--max-memory"], "--max-memory")
        with _errors():
            from esolangs._isolated import check_memory

            check_memory(max_memory, isolated=isolated)
    rest = _split_positional(
        rest,
        set(),
        {
            "--timeout",
            "--seed",
            "--scale",
            "--settings",
            "--set",
            "--portable",
            "--isolated",
            "--max-output",
            "--max-memory",
        },
    )
    seed = _seed_of(options)
    scale = _scale_of(options)
    if flags.count("--isolated") > 1:
        _fail("--isolated given more than once")
    if not (portable and len(rest) == 1):
        _check_count("run", rest, 2)
    if portable and len(rest) == 1:
        path = rest[0]
        with _errors():
            language = _portable_language(path, timeout)
    else:
        language, path = rest[0], rest[1]
    settings = _settings_of(options, set_pairs, language=language)
    # Resolved *before* stdin is read.  It was after, so
    # `esolangs run NotALang prog.txt` with stdin held open blocked forever
    # without ever saying the language was unknown -- the one thing it could
    # have answered without reading a byte.
    with _errors():
        if not portable:
            dialect_options(language, settings)
        facts = describe(language)
        mode = facts["answer_mode"]
        name = facts["name"]
    if mode == "termination" and timeout is None:
        # The default path for these four is an unbounded run of a program
        # written to loop forever, which is a hang with no output and no
        # explanation.  Not refused -- a program whose answer is 0 halts,
        # and running one unbounded is perfectly sensible -- but said aloud.
        sys.stderr.write(
            f"{name}: this language answers 1 by not terminating, so a "
            f"program with that answer will run until you stop it; pass "
            f"--timeout SECONDS to bound it\n"
        )
    program = _read_program(
        path, timeout, language=language, portable=portable, settings=settings
    )
    stdin = _read_stdin(timeout, _stdin_hint(facts))
    try:
        with (
            _UnboundedNotice("run") if timeout is None else _null_context(),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            if isolated:
                output = run(
                    language,
                    program,
                    stdin=stdin,
                    timeout=timeout,
                    seed=seed,
                    scale=scale,
                    isolated=True,
                    max_output=max_output,
                    max_memory=max_memory,
                    settings=settings,
                )
            else:
                output = run(
                    language,
                    program,
                    stdin=stdin,
                    timeout=timeout,
                    seed=seed,
                    scale=scale,
                    settings=settings,
                )
        for entry in caught:
            _note(str(entry.message))
    except TemplateError as exc:
        _fail(_template_hint(exc, language))
    except ExecutionTimeoutError as exc:
        if mode == "termination":
            # The timeout *is* the answer here, so it is not a failure.
            sys.stderr.write(
                f"{exc}\nnote: {name} answers 1 by not terminating, so for a "
                f"generated truth-table program this timeout is the answer 1\n"
            )
            sys.exit(_TIMEOUT_EXIT)
        # Distinct from a program error's 1, following timeout(1), so a
        # script can tell "ran out of time" from "the program broke".  Those
        # shared exit 1, which made the four termination languages'
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
    # A program that printed nothing is a legal program, and also what you
    # get from an empty file or the wrong path.  Say so on a terminal, where
    # the alternative is a blank line and no way to tell the two apart; a
    # pipe still receives exactly the empty output.
    empty = isinstance(program, str) and not program.strip()
    if empty:
        # Legal, and almost never what was meant: an empty file is what you
        # get from a redirect that failed or a generate that was never run.
        # Said on stderr, so a pipeline still receives the empty output.
        _note(f"note: {path} is empty, so there was no program to run")
    if not output and sys.stdout.isatty():
        sys.stderr.write(
            f"{language}: the program ran and printed nothing"
            f"{' (the file is empty)' if empty else ''}\n"
        )
