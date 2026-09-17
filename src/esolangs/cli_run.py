"""``esolangs run``: one program through its interpreter, judged on request."""

from __future__ import annotations

import sys
import warnings

from esolangs import describe, read_answer, run
from esolangs.cli_args import (
    _check_count,
    _fail,
    _pop_options,
    _seed_of,
    _split_positional,
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
    _read_program,
    _read_stdin,
    _UnboundedNotice,
    _write_output,
)
from esolangs.exceptions import EsolangError, ExecutionTimeoutError, TemplateError


def _judge(language: str, output: str, mode: object) -> str:
    """Return the answer bit for a finished run, or exit explaining why not."""
    if mode == "termination":
        # It halted, and halting is this group's 0.  The 1 is the timeout,
        # which never reaches here -- ``_run`` reports it before judging.
        return "0"
    try:
        return read_answer(language, output)
    except EsolangError as exc:
        _fail(str(exc), 1)
        raise  # pragma: no cover - unreachable; _fail exits


def _run(rest: list[str]) -> None:
    """Run a program through its interpreter and write its output."""
    rest, options = _pop_options(rest, {"--timeout", "--table", "--seed"})
    # The value is checked here, before the positionals are counted.  It ran
    # after, so `run --timeout brainfuck prog.txt` -- a forgotten number --
    # swallowed the language as the timeout's value and then reported
    # "missing <program-file>", sending the reader to look at the one
    # argument that was not the problem.
    timeout = _timeout_of(options)
    rest = _split_positional(
        rest, {"--judge"}, {"--timeout", "--judge", "--table", "--seed"}
    )
    seed = _seed_of(options)
    judge = "--judge" in rest
    # Refused like every value-taking option is.  `--judge --judge` was
    # accepted in silence while `--timeout 5 --timeout 9` was refused, and
    # the inconsistency is the finding rather than either policy.
    if rest.count("--judge") > 1:
        _fail("--judge given more than once")
    rest = [arg for arg in rest if arg != "--judge"]
    _check_count("run", rest, 2)
    language, path = rest[0], rest[1]
    program = _read_program(path, timeout)
    # Resolved *before* stdin is read.  It was after, so
    # `esolangs run NotALang prog.txt` with stdin held open blocked forever
    # without ever saying the language was unknown -- the one thing it could
    # have answered without reading a byte.
    try:
        facts = describe(language)
        mode = facts["answer_mode"]
        name = facts["name"]
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    stdin = _read_stdin(timeout, _stdin_hint(facts))
    if mode == "termination" and timeout is None:
        if judge:
            # Judging needs the bound, so this is a refusal rather than the
            # warning below -- and only one of the two is printed.
            _fail(
                f"--judge needs --timeout for {name}: its answer for a 1 is "
                f"that the program never stops, so there is nothing to wait "
                f"for without a bound"
            )
        # The default path for these three is an unbounded run of a program
        # written to loop forever, which is a hang with no output and no
        # explanation.  Not refused -- a program whose answer is 0 halts,
        # and running one unbounded is perfectly sensible -- but said aloud.
        sys.stderr.write(
            f"{name}: this language answers 1 by not terminating, so a "
            f"program with that answer will run until you stop it; pass "
            f"--timeout SECONDS to bound it\n"
        )
    table = options.get("--table")
    warning = _shape_warning(facts, stdin, table)
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
            "one line of bits"
            if facts["input_shape"] == "one_line"
            else "one row index"
        )
        _fail(
            f"{name} reads {reads}, so the bit count cannot be checked from "
            f"stdin alone -- pass --table <truth-table> with --judge, or use: "
            f"esolangs answer {_as_argument(name)} <truth-table> <bits>"
        )
    # No copy of the warning here.  ``run`` emits the same judgement as a
    # ``UserWarning`` now, so printing it as well said everything twice --
    # and Python's default format would have put this file's path and a line
    # of its source in front of it, which is nobody's idea of a CLI message.
    try:
        with (
            _UnboundedNotice("run") if timeout is None else _null_context(),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            output = run(language, program, stdin, timeout, seed)
        surplus = next(
            (str(e.message) for e in caught if "lines supplied" in str(e.message)),
            None,
        )
        if judge and surplus is not None:
            # A surplus read under ``--judge`` is the arity mismatch the
            # flag exists to catch: the answer bit would be for a different
            # row.  Refused *instead of* being rendered as advice, so it is
            # said once rather than twice.
            _fail(f"{surplus}\n(refused because --judge asks for an answer bit)")
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
        # shared exit 1, which made the three termination languages'
        # answer indistinguishable from a crash.
        _emit_partial(exc)
        _fail(str(exc), _TIMEOUT_EXIT)
    except EsolangError as exc:
        # A usage error (an unknown language) is still 2; anything the
        # program itself did is the program's failure, and exits 1.
        _emit_partial(exc)
        _fail(str(exc), _exit_code(exc))
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
    if not program.strip():
        # Legal, and almost never what was meant: an empty file is what you
        # get from a redirect that failed or a generate that was never run.
        # Said on stderr, so a pipeline still receives the empty output.
        _note(f"note: {path} is empty, so there was no program to run")
    if not output and sys.stdout.isatty():
        sys.stderr.write(
            f"{language}: the program ran and printed nothing"
            f"{' (the file is empty)' if not program.strip() else ''}\n"
        )
