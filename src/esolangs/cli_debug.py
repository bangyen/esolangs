"""``esolangs debug``: the breakpoint/watch VM session and its TUI."""

from __future__ import annotations

import sys

from esolangs import check_runnable, describe
from esolangs.cli_args import (
    _check_count,
    _fail,
    _is_int,
    _pop_cell,
    _pop_options,
    _split_positional,
    _timeout_of,
)
from esolangs.cli_hints import (
    _TIMEOUT_EXIT,
    _abridge,
    _shape_warning,
    _stdin_hint,
    _template_hint,
)
from esolangs.cli_io import _null_context, _read_program, _read_stdin, _UnboundedNotice
from esolangs.debugger import make_debugger
from esolangs.exceptions import EsolangError, TemplateError
from esolangs.raster import Raster
from esolangs.tui import breakpoint_for, run_tui


def _run_tui_session(
    language: str,
    program: str | Raster,
    stdin: str,
    options: dict[str, str],
    cell: tuple[int, int] | None,
) -> None:
    """Hand the run to the step-through screen, with what it can draw.

    A *position* goes to the screen as well as to the condition, since it is
    the one kind of breakpoint that can be marked on the program; a cell or
    an output breakpoint is a fact about state with nowhere to put a mark.
    ``--watch-cell`` means the same thing on both sides -- one cell's value
    over time -- and the screen shows it as a row that grows as you step.
    """
    at = (int(options["--break-at"]),) if "--break-at" in options else ()
    stop = breakpoint_for(cell=cell, output=options.get("--break-on-output"))
    watch = int(options["--watch-cell"]) if "--watch-cell" in options else None
    try:
        run_tui(language, program, stdin, stop=stop, at=at, watch=watch)
    except ValueError as exc:
        _fail(str(exc))


def _debug(rest: list[str]) -> None:
    """Run a program under the debugger and report where it stopped."""
    # ``--tui`` is the one bare flag here, and ``_pop_options`` gives every
    # name a value, so it comes out first rather than teaching that helper
    # about a second kind of option for a single caller.
    tui = "--tui" in rest
    rest = [arg for arg in rest if arg != "--tui"]
    options_taken = {
        "--steps",
        "--watch-cell",
        "--break-at",
        "--break-on-cell",
        "--break-on-output",
        "--stdin",
        "--timeout",
        "--table",
    }
    # Options first, then the stray-flag check: a *value* can begin with a
    # dash (``--timeout -inf``), and a check that runs before the pairs are
    # consumed cannot tell one from a flag -- it answered that with
    # "unknown option: -inf" instead of "must be finite".
    rest, options = _pop_options(rest, options_taken)
    # Before the positional count, matching ``run``: a forgotten number made
    # the language the timeout's value and the complaint landed on the file.
    limit = _timeout_of(options)
    rest = _split_positional(rest, set(), options_taken)
    _check_count("debug", rest, 2)
    language, path = rest[0], rest[1]
    for name in ("--steps", "--watch-cell", "--break-at"):
        if name in options and not _is_int(options[name]):
            _fail(f"{name} must be an integer, got {options[name]!r}")
    cell = _pop_cell(options)
    # ``_pop_cell`` accepts ``-1`` as an integer, and the value half of the
    # pair may legitimately be negative; the index half may not -- indexing
    # from the end is not a place a breakpoint can name.  Uncaught, it
    # reached ``check_whole`` and ``main``'s catch-all, which reported a bug
    # in esolangs at exit 70 for a typo.
    if cell is not None and cell[0] < 0:
        _fail(f"--break-on-cell index must not be negative, got {cell[0]}")
    # A negative cell index is Python list indexing leaking through: it
    # printed cell 0's history under the name -1, which is a wrong answer
    # rather than an empty one.  Every other negative here is refused.
    if "--watch-cell" in options and int(options["--watch-cell"]) < 0:
        _fail(f"--watch-cell must not be negative, got {options['--watch-cell']}")
    # A negative bound is not a smaller bound, it is no bound: the run went
    # unbounded, which is the one thing --steps exists to prevent.
    if "--steps" in options and int(options["--steps"]) < 0:
        _fail(f"--steps must not be negative, got {options['--steps']}")
    # And the third one, which was the only integer flag here without a
    # negative guard.  It passed the is-an-integer check above, reached
    # ``Debugger.break_at``'s own validation, and came back out of ``main``'s
    # catch-all as "internal error ... this is a bug in esolangs" at exit
    # 70 -- inviting a bug report for a typo.
    if "--break-at" in options and int(options["--break-at"]) < 0:
        _fail(f"--break-at must not be negative, got {options['--break-at']}")
    program = _read_program(path, limit)
    try:
        facts = describe(language)
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    # The key loop owns the terminal's stdin, so a piped stream cannot also
    # be the program's input: the two would race for the same descriptor.
    # ``--stdin`` is how a TUI run feeds its program instead.
    if tui and not sys.stdin.isatty():
        # Not exempted by ``--stdin``: following that advice turned the
        # refusal into curses failing with ``(19, 'Operation not supported
        # by device')`` at exit 70.  ``--stdin`` is the program's input,
        # not a terminal for the TUI.
        _fail(
            "--tui reads keys from a terminal, and this stdin is not one. "
            "--stdin says where the program's input comes from and does not "
            "substitute; run the TUI from a terminal, or drop --tui and use "
            "--break-at/--break-on-cell/--break-on-output"
        )
    stdin = (
        options["--stdin"]
        if "--stdin" in options
        else ("" if tui else _read_stdin(limit, _stdin_hint(facts)))
    )
    # The same two refusals ``run`` makes.  Debugging a program is no reason
    # to skip them: an unfilled template stepped confidently to `output: '0'`
    # and reported a wrong answer with no warning at all, and a load error
    # escaped as a traceback from the one command whose whole promise is to
    # report a fault rather than propagate it.
    try:
        check_runnable(language, program)
        if tui:
            # Built through the same refusals, then handed to the screen --
            # which owns the stepping from here, so nothing below runs.
            _run_tui_session(language, program, stdin, options, cell)
            return
        dbg = make_debugger(language, program, stdin)
    except TemplateError as exc:
        _fail(_template_hint(exc, language))
    except EsolangError as exc:
        _fail(str(exc))
    except ValueError as exc:
        _fail(f"{language}: {exc}")
    breakpoints_set = False
    if "--break-on-output" in options:
        if not options["--break-on-output"]:
            _fail("--break-on-output needs some text; every output contains ''")
        dbg.break_on_output(options["--break-on-output"])
        breakpoints_set = True
    # A position and a cell are the other two conditions ``Debugger`` has
    # always had, and they are wired here as well as into the screen so the
    # two agree about what can be asked for -- a flag that worked under
    # ``--tui`` and nowhere else would be the stranger arrangement.
    if "--break-at" in options:
        dbg.break_at(int(options["--break-at"]))
        breakpoints_set = True
    if cell is not None:
        dbg.break_on_cell(*cell)
        breakpoints_set = True
    watched = int(options["--watch-cell"]) if "--watch-cell" in options else None
    history = dbg.watch_cell(watched) if watched is not None else None
    steps = int(options["--steps"]) if "--steps" in options else None
    # A debugged program is one the caller is already unsure of, so a raise
    # here is a result to report rather than a crash to propagate: the
    # state up to the fault is the thing they asked to see.
    fault = None
    reason = None
    warning = _shape_warning(describe(language), stdin, options.get("--table"))
    if warning:
        sys.stderr.write(f"{warning}\n")
    # ``run`` gained this last round and ``debug`` did not, so `debug 123
    # prog.txt` -- the command you reach for precisely when something is
    # not stopping -- still hung with nothing on screen.  ``--steps`` counts
    # as a bound here as much as ``--timeout`` does, so a run that has one
    # is not told to pass one.
    bounded = steps is not None or limit is not None
    if describe(language)["answer_mode"] == "termination" and not bounded:
        sys.stderr.write(
            f"{describe(language)['name']}: this language answers 1 by not "
            f"terminating, so a program with that answer will run until you "
            f"stop it; pass --timeout SECONDS or --steps N to bound it\n"
        )
    try:
        with _UnboundedNotice("debug") if not bounded else _null_context():
            reason = dbg.run(steps, limit)
    except Exception as exc:
        fault = f"{type(exc).__name__}: {exc}"

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
        if set(values) <= {None}:
            untouched = " (never written)"
        elif None in values:
            untouched = " (None: the cell did not exist yet at that step)"
        else:
            untouched = ""
        if set(values) <= {None}:
            # Verdict first, and no wall of Nones: a never-written cell used
            # to print four hundred of them and put "(never written)" at the
            # far right of a wrapped line.
            print(
                f"cell {options['--watch-cell']}: never written in "
                f"{len(values)} step(s)"
            )
        else:
            print(f"cell {options['--watch-cell']}: {_abridge(values)}{untouched}")
    if fault is not None:
        print(f"raised: {fault}")
        # 1, like ``run``: the program itself failed.  This exited 0 for
        # every outcome -- a clean halt, a timeout and a crash alike -- so a
        # script could not tell them apart without parsing the report.
        sys.exit(1)
    if reason == "timeout":
        sys.exit(_TIMEOUT_EXIT)
