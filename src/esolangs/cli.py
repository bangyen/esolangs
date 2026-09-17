"""Command-line interface for the esolangs package.

Subcommands:
    esolangs list                         list the supported languages
    esolangs describe <language>          print its input shape and where
                                          the answer lands
    esolangs encode <language> <bits>     print the stdin those bits need
    esolangs generate <language> <table>  print a program computing a table
                                          (``--width N`` wraps it to N columns)
    esolangs run <language> <file>        run a program through its interpreter
                                          (``--judge`` prints the answer bit)
    esolangs read-answer <language>       print the answer bit in a program's
                                          output, read from stdin
    esolangs debug <language> <file>      run under the breakpoint/watch VM

Every subcommand takes ``--help``.  For anything else, invoke the module
directly with ``python -m``.

``describe`` and ``read-answer`` are here because the two facts that decided
every wrong answer this tool ever handed out -- how a language wants its
input bits, and where in the output its answer sits -- were readable from
Python and from nowhere else.  A shell user could run all nine of the
languages that do not simply print their answer, and could not judge one of
them: A Painter Ant's answer is a mark on one cell of an eleven-line grid.

Exit codes separate the failures a caller handles differently: **2** is a
usage error (an unknown command, option, or language -- nothing ran), **1**
is the program's own failure (it read past its input, halted on an invalid
operation, was a template), and **124** is a run stopped by ``--timeout``,
after timeout(1) -- from every command that takes one, not only ``run`` and
``debug``.  That last one used to be 1 as well, which left the three
languages whose answer *is* a timeout indistinguishable from a crash, and
then stayed 1 in ``evaluate``, ``verify`` and ``answer`` after the other
two were fixed, which left a script unable to use one code for the event.  Only
an unexpected error still reaches the terminal as a traceback, which is what
a traceback should mean.
"""

from __future__ import annotations

import json
import sys
import warnings

from esolangs import (
    __version__,
    check_runnable,
    check_stdin,
    describe,
    encode_inputs,
    evaluate,
    generate,
    instantiate,
    list_languages,
    read_answer,
    run,
)
from esolangs import spec as _spec
from esolangs.cli_args import (
    _check_count,
    _fail,
    _is_int,
    _pop_cell,
    _pop_options,
    _pop_width,
    _seed_of,
    _split_positional,
    _timeout_of,
)
from esolangs.cli_help import (
    HELP,
    USAGE,
)
from esolangs.cli_hints import (
    _TIMEOUT_EXIT,
    _UNCOUNTABLE_SHAPES,
    _abridge,
    _as_argument,
    _did_you_mean,
    _diverging_answer,
    _exit_code,
    _input_sentence,
    _looks_like_a_table,
    _shape_warning,
    _shell_hint,
    _stdin_hint,
    _swapped_hint,
    _template_hint,
)

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach
# it by this name.  Re-exported in the ``x as x`` form so a caller that
# does not care where a piece lives need not know.
from esolangs.cli_io import (
    _UNBOUNDED_NOTICE_AFTER as _UNBOUNDED_NOTICE_AFTER,
)
from esolangs.cli_io import (
    _bounded_read as _bounded_read,
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
from esolangs.cli_io import (
    _smuggled_bytes as _smuggled_bytes,
)
from esolangs.cli_io import (
    _WaitingNotice as _WaitingNotice,
)
from esolangs.debugger import make_debugger
from esolangs.exceptions import (
    EsolangError,
    ExecutionTimeoutError,
    GeneratorCapError,
    TemplateError,
)
from esolangs.registry import LANGUAGES
from esolangs.tui import breakpoint_for, run_tui


def _encode(rest: list[str]) -> None:
    """Print the stdin that feeds a language its input bits."""
    rest = _split_positional(rest, set())
    _check_count("encode", rest, 2)
    language, bits = rest[0], rest[1]
    if set(bits) - {"0", "1"} or not bits:
        _fail(f"bits must be a string of 0s and 1s, got {bits!r}")
    try:
        sys.stdout.write(encode_inputs(language, [int(bit) for bit in bits]))
    except EsolangError as exc:
        _fail(_shell_hint(str(exc), language))


def _list(rest: list[str]) -> None:
    """Print the supported languages, optionally with capability markers."""
    rest = _split_positional(rest, {"--details", "--json"})
    details = "--details" in rest
    as_json = "--json" in rest
    _check_count("list", [a for a in rest if a not in {"--details", "--json"}], 0)
    if as_json:
        if not details:
            print(json.dumps(list_languages(), indent=2))
            return
        print(
            json.dumps(
                [
                    {
                        "name": name,
                        # The three the marker column encodes, spelled out.
                        "boolean_generator": facts["boolean_generator"],
                        "parameterized": facts["parameterized"],
                        "has_example": bool(facts["examples"]),
                    }
                    for name, facts in (
                        (name, describe(name)) for name in list_languages()
                    )
                ],
                indent=2,
            )
        )
        return
    if not details:
        for name in list_languages():
            print(name)
        return
    width = max(len(name) for name in LANGUAGES)
    # The legend lived in `list --help` only, so the marker columns arrived
    # unexplained for anyone who ran the thing before reading about it.
    print(f"{'language'.ljust(width)}  gen=generator tmpl=template ex=example")
    for name in list_languages():
        facts = describe(name)
        marks = " ".join(
            filter(
                None,
                (
                    "gen" if facts["boolean_generator"] else "",
                    "tmpl" if facts["parameterized"] else "",
                    "ex" if facts["examples"] else "",
                ),
            )
        )
        print(f"{name.ljust(width)}  {marks}")


def _run_tui_session(
    language: str,
    program: str,
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
        # Not exempted by ``--stdin``.  The exemption was the bug: this
        # guard's own message told you to pass ``--stdin``, and doing so
        # turned the clean refusal into curses failing with ``(19,
        # 'Operation not supported by device')`` through the catch-all, at
        # exit 70.  Following the advice was the way to reach the crash.
        #
        # ``--stdin`` settles where the *program's* input comes from; it
        # cannot conjure a terminal to read keys from, which is what the
        # TUI needs and what a pipe or a CI job does not have.
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
    # Exit codes below, after the report is printed: a script that cannot
    # tell a clean halt from a crash has to parse prose, and `run` has had
    # this taxonomy for several rounds.  The state up to the fault is still
    # printed either way, which is the whole point of the command.
    # Always printed, so a script reading fixed field positions does not
    # break on the one case it most wants to parse.
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


def _generate(rest: list[str]) -> None:
    """Print a program computing a truth table."""
    rest, options = _pop_options(rest, {"--bits"})
    before = list(rest)
    rest, width, bare = _pop_width(rest)
    rest = _split_positional(rest, set(), {"--bits", "--width"})
    # `--width` takes an *optional* N, so a truth table typed straight after
    # it is consumed as the width and the report lands on the table being
    # missing -- which is baffling when you did type one.
    eaten = ""
    if width is not None and not bare:
        for i, arg in enumerate(before[:-1]):
            value = before[i + 1]
            if arg == "--width" and _looks_like_a_table(value):
                eaten = (
                    f"\n\nnote: --width consumed {value!r}, which looks like a "
                    f"truth table; put the table after the language"
                )
    _check_count("generate", rest, 2, bare_width=bare, eaten=eaten)
    try:
        # Widthed at both ends, and that is not a mistake.  ``generate``
        # wraps the template (or hands the width to a *layout* language
        # like COD, which lays it out), and ``instantiate`` wraps a program
        # filled from an unwrapped template; a wrapped one fills in place.
        program = generate(rest[0], rest[1], width)
        if "--bits" in options:
            bits = options["--bits"]
            if set(bits) - {"0", "1"} or not bits:
                _fail(f"--bits must be a string of 0s and 1s, got {bits!r}")
            program = instantiate(rest[0], program, [int(b) for b in bits], width)
    except EsolangError as exc:
        _fail(f"{exc}{_swapped_hint(rest[0], rest[1])}")
    if (width is not None or bare) and describe(rest[0])["width_effect"] == "none":
        # Silently ignoring the flag was the sharpest half of the width
        # confusion: two identical programs, one of which was asked to be
        # narrower.  The languages that ignore it have semantic newlines or
        # reject them outright, so honouring it is not on the table --
        # saying so is.
        sys.stderr.write(
            f"note: --width has no effect on {describe(rest[0])['name']} -- "
            f"its newlines are part of the program, so it is emitted as the "
            f"generator built it\n"
        )
    print(program)


def _describe(rest: list[str]) -> None:
    """Print a language's input shape, answer location and capabilities."""
    rest = _split_positional(rest, {"--json", "--spec"})
    as_json = "--json" in rest
    as_spec = "--spec" in rest
    rest = [a for a in rest if a not in {"--json", "--spec"}]
    _check_count("describe", rest, 1)
    try:
        facts = describe(rest[0])
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    if as_spec:
        # Printed rather than folded into the record, because it is prose
        # of a few thousand characters and would swamp every other field.
        text = _spec(str(facts["name"]))
        print(json.dumps({**facts, "spec": text}, indent=2) if as_json else text)
        return
    if as_json:
        # Verbatim, including the keys the reading layout hides: a caller
        # asking for JSON is not reading it, and a field that vanishes when
        # it is empty is the thing that makes a schema unusable.
        print(json.dumps(facts, indent=2))
        return
    # A template language reads no stdin, so its input shape and alphabet
    # are noise -- and ``input_shape`` is the field the README tells you to
    # trust.  Hidden here rather than dropped from ``describe()``, whose
    # keys stay uniform across all 65: a caller that iterates them without
    # branching is the pattern this package spent four rounds proving, and
    # a per-language schema would break it.
    hidden = set()
    if not facts["reads_input"] and facts["parameterized"]:
        hidden = {"input_shape", "input_encoding"}
    width = max(len(key) for key in facts)
    for key, value in facts.items():
        if value is None or value == "" or key in hidden:
            continue
        shown = "\n".join(str(v) for v in value) if isinstance(value, list) else value
        if isinstance(value, tuple):
            shown = " ".join(str(v) for v in value)
        print(f"{key.ljust(width)}  {shown}")
    if hidden:
        print(
            f"{'input'.ljust(width)}  none -- this generator embeds the bits "
            f"in the program: esolangs generate --bits <bits> "
            f"{_as_argument(str(facts['name']))} <table>"
        )
    else:
        # The symmetric row.  A reader had ``input_encoding`` and
        # ``input_shape`` and had to compose them, while the template
        # languages got a sentence -- so the languages where getting it
        # wrong is possible were the ones told least plainly.
        print(f"{'input'.ljust(width)}  {_input_sentence(facts)}")
    # Every field above is about driving a *generated* program.  Someone
    # writing their own needs the language's command table, which this
    # package ships as the interpreter's module docstring and used to name
    # only as ``interpreter: stack_based.unsquare`` -- an import path, with
    # no hint that importing it is the point.
    print(
        f"{'spec'.ljust(width)}  esolangs describe --spec "
        f"{_as_argument(str(facts['name']))}"
    )


def _check_stdin(rest: list[str]) -> None:
    """Judge stdin against a language's declared shape, running nothing."""
    rest, options = _pop_options(rest, {"--table"})
    rest = _split_positional(rest, set(), {"--table"})
    _check_count("check-stdin", rest, 1)
    language = rest[0]
    try:
        facts = describe(language)
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    stdin = _read_stdin(hint="; pipe the input in, or close stdin")
    table = options.get("--table")
    try:
        check_stdin(str(facts["name"]), stdin, table)
    except EsolangError as exc:
        _fail(str(exc))


def _read_answer(rest: list[str]) -> None:
    """Read a program's output on stdin and print the answer bit in it."""
    rest = _split_positional(rest, set())
    _check_count("read-answer", rest, 1)
    language = rest[0]
    try:
        facts = describe(language)
    except EsolangError as exc:
        _fail(str(exc))
        raise  # pragma: no cover - unreachable; _fail exits
    if facts["answer_mode"] == "termination":
        polarity = facts["answer_encoding"]
        zero, one = polarity
        _fail(
            f"{facts['name']} answers by {zero} for a 0 and {one} for a 1, so "
            f"there is no output to read; use: esolangs run --judge "
            f"--timeout <seconds> {facts['name']} <program-file>"
        )
    output = _read_stdin(hint="; pipe a program's output in, or close stdin")
    if not output.strip():
        _fail(
            f"nothing on stdin to read an answer out of; pipe a program's "
            f"output in: esolangs run {language} prog.txt | esolangs "
            f"read-answer {language}"
        )
    try:
        print(read_answer(language, output))
    except EsolangError as exc:
        _fail(str(exc))


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
        if facts["parameterized"]:
            source, stdin = instantiate(name, program, row, truth_table=table), ""
        else:
            source, stdin = program, encode_inputs(name, row, table)
        if facts["answer_mode"] == "termination":
            # A bound is the answer here rather than a safeguard, so one is
            # supplied: this command exists to be a one-liner, and making a
            # reader discover that three of the sixty-five need a flag would
            # defeat that.
            print(_diverging_answer(name, source, stdin, timeout or 5.0, facts))
            return
        print(read_answer(name, run(name, source, stdin, timeout)))
    except EsolangError as exc:
        # No ``TemplateError`` clause: this command generates the template
        # and fills it in the same breath, so it never hands an unfilled one
        # on -- the same reason ``evaluate`` has none.
        _fail(str(exc), _exit_code(exc))


def _evaluate(rest: list[str]) -> None:
    """Print the table a generated program actually computes."""
    _run_round_trip(rest, "evaluate")


def _verify(rest: list[str]) -> None:
    """Report whether a generated program computes the table asked for."""
    _run_round_trip(rest, "verify")


def _run_round_trip(rest: list[str], command: str) -> None:
    """Shared body of ``verify`` and ``evaluate``.

    One function because they differ only in what they print: the work --
    generate, walk every row, encode, run, read the answer -- is the same,
    and is the thing a CLI-only user had to write a shell loop for.
    """
    rest, options = _pop_options(rest, {"--timeout"})
    timeout = _timeout_of(options)
    before = list(rest)
    rest, width, bare = _pop_width(rest)
    rest = _split_positional(rest, set(), {"--timeout", "--width"})
    # The same trap ``generate`` carries: ``--width`` takes an *optional* N,
    # so a truth table typed straight after it is eaten as the width and the
    # complaint lands on a missing table.
    eaten = ""
    if width is not None and not bare:
        for i, arg in enumerate(before[:-1]):
            value = before[i + 1]
            if arg == "--width" and _looks_like_a_table(value):
                eaten = (
                    f"\n\nnote: --width consumed {value!r}, which looks like a "
                    f"truth table; put the table after the language"
                )
    _check_count(command, rest, 2, bare_width=bare, eaten=eaten)
    language, table = rest[0], rest[1]
    try:
        computed = evaluate(language, table, timeout, width)
    except GeneratorCapError as exc:
        # Nothing ran, so this is the usage class: the generator refused the
        # table rather than building a program that got the wrong answer.
        _fail(str(exc))
    except EsolangError as exc:
        # No ``TemplateError`` clause: this command never hands an unfilled
        # template on, because ``evaluate`` reads ``parameterized`` and
        # fills the slots itself.
        _fail(str(exc), _exit_code(exc))
    if command == "evaluate":
        print(computed)
        return
    if computed == table:
        print("ok")
        return
    # The computed table beside the wanted one, because which rows disagree
    # is the whole content of a failure here.
    differing = [
        i for i, (a, b) in enumerate(zip(computed, table, strict=True)) if a != b
    ]
    _fail(
        f"computed {computed}, wanted {table}\n"
        f"{len(differing)} row(s) disagree: {', '.join(map(str, differing))}",
        1,
    )


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
        # ``--judge`` is the caller saying "this is a truth-table program and
        # I want its answer bit", so a stdin the language cannot read the way
        # they meant is a usage error rather than advice: the whole output of
        # this command would be one wrong digit.  Plain ``run`` only warns,
        # because it executes arbitrary programs of the language and the
        # shape this calls wrong may be exactly what one of them wants.
        #
        # That split is the answer to "warn or refuse?" -- the flag says
        # which of the two situations you are in.
        _fail(f"{warning}\n(refused because --judge asks for an answer bit)")
    if judge and table is None and facts["input_shape"] in _UNCOUNTABLE_SHAPES:
        # Last, after the specific diagnoses above.  Put first, this swallowed
        # them: `abc` fed to Fargo was answered with "pass --table" instead of
        # "reads one decimal row index", which is the more useful of the two
        # by a wide margin.  So this only speaks when nothing else has -- when
        # the stdin is a perfectly good single line and the only thing that
        # cannot be checked is how many bits it should hold.
        #
        # A refusal rather than advice, and only for these two shapes.  The
        # first draft printed a note on every `--judge` call without a table,
        # including the ones where nothing was wrong, and a warning that fires
        # on correct input is worth less than no warning at all.  The other
        # sixty-seven read a line at a time, so `run` counts what the program
        # took against what it was given and catches a mismatch after the
        # fact; these two read a single line and never run off an end to
        # count.
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
        # The count and range checks `--table` buys.  ``run`` warns through
        # the library, which is not given the table and so can only judge
        # shape and alphabet -- so `run --table` computed this and used it
        # for nothing, while `check-stdin --table` and `run --judge --table`
        # both refused the same stdin.  Three routes, two answers.
        #
        # Only when the library did not already say it: a shape complaint
        # comes back from both, and saying it twice is what the note-vs-
        # warning split was cleaned up to stop.
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


def main() -> None:
    """Dispatch the ``esolangs`` subcommands, and handle an interrupt.

    ``KeyboardInterrupt`` is caught here because this tool *invites* it:
    on a language that answers by not terminating it prints "will run until
    you stop it", and then dumped a traceback when the reader did. 130 is
    the shell convention for a command killed by SIGINT.

    ``BrokenPipeError`` likewise: ``esolangs generate ... | head`` is an
    ordinary thing to type, and closing the pipe before the first write
    left ``Exception ignored while flushing sys.stdout`` on the terminal
    and exit 120.

    Anything else is a bug in this package rather than in the program
    being run, and exits 70 with a one-line report instead of a
    traceback.
    """
    try:
        _dispatch()
        # Flushed here, where the failure is catchable.  Python flushes
        # stdout again during interpreter shutdown, and a pipe closed
        # before the first write made *that* print "Exception ignored
        # while flushing sys.stdout" after the command had otherwise
        # finished.
        sys.stdout.flush()
    except KeyboardInterrupt:
        sys.stderr.write("interrupted\n")
        sys.exit(130)
    except BrokenPipeError:  # pragma: no cover - needs a closed pipe
        # Python flushes stdout at exit and would report the same error
        # again from the interpreter's own teardown; pointing it at
        # ``devnull`` is the documented way to stop that.
        import os

        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(120)
    except Exception as exc:
        # Every *deliberate* failure is an ``EsolangError`` and is handled
        # where it happens; anything reaching here is a bug in this
        # package.  That used to mean the reader got a traceback -- an
        # out-of-range address in three interpreters raised ``OverflowError``
        # straight through ``main``.  A traceback is the right signal that
        # something is broken and the wrong thing to hand a user, so it
        # becomes a one-line report and an exit code nothing else uses.
        sys.stderr.write(
            f"internal error: {type(exc).__name__}: {exc}\n"
            f"This is a bug in esolangs, not in your program; please report "
            f"it with the command you ran.\n"
        )
        sys.exit(70)


def _dispatch() -> None:
    """Dispatch the ``esolangs`` subcommands."""
    argv = sys.argv[1:]
    if not argv:
        sys.stderr.write(USAGE)
        sys.exit(2)

    cmd, rest = argv[0], argv[1:]
    # Accepted after a subcommand too.  The top-level help advertises it
    # without saying where it goes, and `esolangs list --version` answering
    # "unknown option" is a strange way to learn that.
    if {"--version", "-V"} & set(argv):
        print(f"esolangs {__version__}")
        sys.exit(0)
    if cmd in ("--help", "-h", "help"):
        sys.stdout.write(HELP[rest[0]] if rest and rest[0] in HELP else USAGE)
        sys.exit(0)
    if cmd not in HELP:
        # Languages and options both suggest a near miss; the subcommands
        # they are typed after did not, so `esolangs lst` got the whole
        # usage block and no hint that `list` was one letter away.
        _fail(f"unknown command: {cmd}{_did_you_mean(cmd, set(HELP))}\n\n{USAGE}")
    if {"--help", "-h"} & set(rest):
        sys.stdout.write(HELP[cmd])
        sys.exit(0)

    {
        "list": _list,
        "describe": _describe,
        "encode": _encode,
        "generate": _generate,
        "run": _run,
        "read-answer": _read_answer,
        "check-stdin": _check_stdin,
        "answer": _answer,
        "verify": _verify,
        "evaluate": _evaluate,
        "debug": _debug,
    }[cmd](rest)


if __name__ == "__main__":
    main()
