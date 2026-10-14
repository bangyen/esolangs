"""``esolangs debug``: the breakpoint/watch VM session."""

from __future__ import annotations

import sys
from contextlib import nullcontext

from esolangs import _check_runnable, describe
from esolangs.cli.args import (
    _errors,
    _fail,
    _integer,
    _nonnegative,
    _pop_cell,
    _pop_options,
    _pop_portable,
    _pop_set_pairs,
    _settings_of,
    _split_positional,
    _timeout_of,
)
from esolangs.cli.hints import (
    _TIMEOUT_EXIT,
    _abridge,
    _stdin_hint,
    _template_hint,
)
from esolangs.cli.io import (
    _read_program,
    _read_stdin,
    _resolve_target,
    _termination_notice,
    _unbounded_notice,
)
from esolangs.debugger import make_debugger
from esolangs.exceptions import EsolangError, TemplateError
from esolangs.runtime.source_hints import error_text
from esolangs.settings import dialect_options


def _debug(rest: list[str]) -> None:
    """Run a program under the debugger and report where it stopped."""
    options_taken = {
        "--steps",
        "--watch-cell",
        "--break-at",
        "--break-on-cell",
        "--break-on-output",
        "--stdin",
        "--timeout",
        "--settings",
        "--set",
    }
    # Options first, then the stray-flag check: a *value* can begin with a
    # dash (``--timeout -inf``), and a check that runs before the pairs are
    # consumed cannot tell one from a flag -- it answered that with
    # "unknown option: -inf" instead of "must be finite".
    rest, set_pairs = _pop_set_pairs(rest)
    rest, options = _pop_options(rest, options_taken)
    rest, portable = _pop_portable(rest)
    # Before the positional count, matching ``run``: a forgotten number made
    # the language the timeout's value and the complaint landed on the file.
    limit = _timeout_of(options)
    rest = _split_positional(rest, set(), options_taken | {"--portable"})
    language, path, content = _resolve_target("debug", rest, limit, portable=portable)
    numbers = {
        name: _integer(options[name], name)
        for name in ("--watch-cell", "--steps", "--break-at")
        if name in options
    }
    cell = _pop_cell(options)
    # The breakpoint value may be negative; its cell index may not.
    if cell is not None:
        _nonnegative(cell[0], "--break-on-cell index", cell[0])
    for name, number in numbers.items():
        _nonnegative(number, name, options[name])
    settings = _settings_of(options, set_pairs, language=language)
    with _errors():
        if not portable:
            dialect_options(language, settings)
        facts = describe(language)
    program = _read_program(
        path,
        limit,
        language=language,
        portable=portable,
        settings=settings,
        content=content,
    )
    stdin = (
        options["--stdin"]
        if "--stdin" in options
        else _read_stdin(limit, _stdin_hint(facts))
    )
    # The same two refusals ``run`` makes.  Debugging a program is no reason
    # to skip them: an unfilled template stepped confidently to `output: '0'`
    # and reported a wrong answer with no warning at all, and a load error
    # escaped as a traceback from the one command whose whole promise is to
    # report a fault rather than propagate it.
    try:
        _check_runnable(language, program)
        dbg = make_debugger(language, program, stdin=stdin, settings=settings)
    except TemplateError as exc:
        _fail(_template_hint(exc, language))
    except EsolangError as exc:
        _fail(exc)
    except ValueError as exc:
        _fail(f"{language}: {exc}")
    breakpoints_set = False
    if "--break-on-output" in options:
        if not options["--break-on-output"]:
            _fail("--break-on-output needs some text; every output contains ''")
        dbg.break_on_output(options["--break-on-output"])
        breakpoints_set = True
    if "--break-at" in numbers:
        dbg.break_at(numbers["--break-at"])
        breakpoints_set = True
    if cell is not None:
        dbg.break_on_cell(*cell)
        breakpoints_set = True
    watched = numbers.get("--watch-cell")
    history = dbg.watch_cell(watched) if watched is not None else None
    steps = numbers.get("--steps")
    # A debugged program is one the caller is already unsure of, so a raise
    # here is a result to report rather than a crash to propagate: the
    # state up to the fault is the thing they asked to see.
    fault = None
    reason = None
    # ``run`` gained this last round and ``debug`` did not, so `debug brainfuck
    # prog.txt` -- the command you reach for precisely when something is
    # not stopping -- still hung with nothing on screen.  ``--steps`` counts
    # as a bound here as much as ``--timeout`` does, so a run that has one
    # is not told to pass one.
    bounded = steps is not None or limit is not None
    if facts["answer_mode"] == "termination" and not bounded:
        _termination_notice(facts["name"], "--timeout SECONDS or --steps N")
    try:
        with _unbounded_notice("debug") if not bounded else nullcontext():
            reason = dbg.run(max_steps=steps, timeout=limit)
    except Exception as exc:
        fault = f"{type(exc).__name__}: {error_text(exc)}"

    if breakpoints_set and reason != "breakpoint":
        # A breakpoint that never fires looks exactly like a program that
        # never reached it, and the report said nothing either way.
        sys.stderr.write("note: no breakpoint matched during this run\n")
    print(f"halted: {'yes' if dbg.halted else 'no'}")
    # Exit codes after the report, so a script need not parse prose; the
    # state up to the fault is always printed, in fixed field positions.
    print(f"stopped: {reason if reason is not None else 'raised'}")
    print(f"ip: {dbg.ip}")
    print(f"output: {dbg.output!r}")
    if history is not None:
        values = list(history)
        # A `None` means the cell did not exist yet at that step -- the tape
        # had not grown that far, or the language has no such store.  The
        # all-`None` case was annotated and the *mixed* case was not, which
        # is the one where a reader actually needs telling: a row reading
        # `[None, None, 0, 0, ...]` otherwise looks like a value.
        label = options["--watch-cell"]
        if set(values) <= {None}:
            # Verdict first, and no wall of Nones: a never-written cell used
            # to print four hundred of them and put "(never written)" at the
            # far right of a wrapped line.
            print(f"cell {label}: never written in {len(values)} step(s)")
        else:
            untouched = (
                " (None: the cell did not exist yet at that step)"
                if None in values
                else ""
            )
            print(f"cell {label}: {_abridge(values)}{untouched}")
    if fault is not None:
        print(f"raised: {fault}")
        # 1, like ``run``: the program itself failed.  This exited 0 for
        # every outcome -- a clean halt, a timeout and a crash alike -- so a
        # script could not tell them apart without parsing the report.
        sys.exit(1)
    if reason == "timeout":
        sys.exit(_TIMEOUT_EXIT)
