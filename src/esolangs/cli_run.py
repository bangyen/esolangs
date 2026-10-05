"""``esolangs run``: one program through its interpreter, judged on request."""

from __future__ import annotations

import sys
import warnings

from esolangs import describe, read_answer, run
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
    _table_of,
    _timeout_of,
)
from esolangs.cli_hints import (
    _TIMEOUT_EXIT,
    _UNCOUNTABLE_SHAPES,
    _as_argument,
    _exit_code,
    _shape_warning,
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


def _judge(language: str, output: str, mode: object) -> str:
    """Return the answer bit for a finished run, or exit explaining why not."""
    if mode == "termination":
        # It halted, and halting is this group's 0.  The 1 is the timeout,
        # which never reaches here -- ``_run`` reports it before judging.
        return "0"
    try:
        return read_answer(language, output)
    except EsolangError as exc:
        _fail(exc, 1)
        raise  # pragma: no cover - unreachable; _fail exits


def _run(rest: list[str]) -> None:
    """Run a program through its interpreter and write its output."""
    rest, set_pairs = _pop_set_pairs(rest)
    rest, options = _pop_options(
        rest,
        {
            "--timeout",
            "--table",
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
    rest, flags = _pop_flags(rest, {"--judge", "--isolated"})
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
            "--judge",
            "--table",
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
    judge = "--judge" in flags
    # Refused like every value-taking option is.  `--judge --judge` was
    # accepted in silence while `--timeout 5 --timeout 9` was refused, and
    # the inconsistency is the finding rather than either policy.
    for flag in ("--judge", "--isolated"):
        if flags.count(flag) > 1:
            _fail(f"{flag} given more than once")
    if not (portable and len(rest) == 1):
        _check_count("run", rest, 2)
    if portable and len(rest) == 1:
        path = rest[0]
        with _errors():
            language = _portable_language(path, timeout)
    else:
        language, path = rest[0], rest[1]
    settings = _settings_of(options, set_pairs, language=language)
    table = _table_of(options)
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
        if judge:
            # Judging needs the bound, so this is a refusal rather than the
            # warning below -- and only one of the two is printed.
            _fail(
                f"--judge needs --timeout for {name}: its answer for a 1 is "
                f"that the program never stops, so there is nothing to wait "
                f"for without a bound"
            )
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
    warning = _shape_warning(facts, stdin, table) if judge or table is not None else ""
    if warning and judge:
        # ``--judge`` wants one answer bit, so a bad stdin is a usage error
        # (the output would be one wrong digit); plain ``run`` only warns,
        # since an arbitrary program may want that shape.
        _fail(f"{warning}\n(refused because --judge asks for an answer bit)")
    if judge and table is None and facts["input_shape"] in _UNCOUNTABLE_SHAPES:
        # Last: put first it swallowed the specific diagnoses (``abc`` to
        # Fargo said "pass --table" instead of "reads one decimal row
        # index").  A refusal, only for these two single-line shapes, which
        # never run off an end for ``run`` to count; a note on every
        # table-less ``--judge`` fired on correct input.
        reads = (
            "a stream of bit characters"
            if facts["input_shape"] == "char_stream_cyclic"
            else "one row index"
        )
        _fail(
            f"{name} reads {reads}, so the bit count cannot be checked from "
            f"stdin alone -- pass --table <truth-table> with --judge, or "
            f"check a saved program with: esolangs evaluate --table "
            f"<truth-table> {_as_argument(name)} <program-file>"
        )
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
                    stdin,
                    timeout,
                    seed,
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
                    stdin,
                    timeout,
                    seed,
                    scale=scale,
                    settings=settings,
                )
        for entry in caught:
            _note(str(entry.message))
        # The count and range checks ``--table`` buys; the library judges
        # only shape and alphabet, so ``run --table`` used the table for
        # nothing while the other two routes refused.  Skipped when the
        # library already said it.
        said = {str(entry.message) for entry in caught}
        if (
            warning
            and warning not in said
            and not any(warning.startswith(one.rstrip(".")) for one in said)
        ):
            _note(warning)
    except TemplateError as exc:
        _fail(_template_hint(exc, language))
    except ExecutionTimeoutError as exc:
        if mode == "termination":
            # The timeout *is* the answer here, so it is not a failure.
            if judge:
                print("1")
                return
            sys.stderr.write(
                f"{exc}\nnote: {name} answers 1 by not terminating, so for a "
                f"generated truth-table program this timeout is the answer 1"
                f" -- `--judge` prints it as one\n"
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
    if judge:
        print(_judge(language, output, mode))
        return
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
